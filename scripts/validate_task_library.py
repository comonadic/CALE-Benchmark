#!/usr/bin/env python3
"""Validate active research cards without executing tasks or fetching sources."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as error:
    raise SystemExit('Install task-library/requirements.txt before running this validator.') from error

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    'task_type_id', 'industry', 'work_family', 'title', 'role', 'trigger',
    'expert_time_estimate', 'workflow_steps', 'software', 'deliverables',
    'verification', 'input_data', 'fusable_with', 'evidence', 'status',
    'instantiated_tasks', 'notes',
}
FULL_TEXT = {'full_text', 'full_text_official_republication', 'full_text_attributed_republication'}
SUPPORTS = {'role', 'trigger', 'workflow_steps', 'deliverables', 'verification', 'software'}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key {key!r}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(library: Path):
    errors, cards, paths, fingerprints, evidence_registry = [], {}, {}, {}, {}
    for industry, prefix in [('finance', 'FIN'), ('legal', 'LAW')]:
        source_index = ROOT / 'skills' / f'{"finance" if industry == "finance" else "legal"}-task-authoring' / 'references/sources.md'
        text = source_index.read_text()
        source_ids = set(re.findall(r'^### (S\d{2}) ', text, re.M))
        family_ids = set(re.findall(r'^### ([FL]\d{2}) ', text, re.M))
        for file in sorted((library / industry).glob('*/*.yaml')):
            relative = str(file.relative_to(library))
            def check(condition, message):
                if not condition:
                    errors.append(f'{relative}: {message}')
            try:
                card = yaml.load(file.read_text(), Loader=UniqueKeyLoader)
            except (yaml.YAMLError, ValueError) as error:
                errors.append(f'{relative}: invalid YAML: {error}')
                continue
            if not isinstance(card, dict):
                errors.append(f'{relative}: expected a mapping')
                continue
            missing = REQUIRED - card.keys()
            check(not missing, f'missing fields {sorted(missing)}')
            if missing:
                continue
            card_id = card['task_type_id']
            check(nonempty(card_id), 'task_type_id must be a string')
            if not isinstance(card_id, str):
                continue
            match = re.fullmatch(rf'{prefix}-([FL]\d{{2}})-\d{{3}}', card_id)
            check(match is not None, 'invalid ID or industry prefix')
            check(card_id not in cards, 'duplicate task_type_id')
            check(card['industry'] == industry, 'industry must match directory')
            check(file.stem == card_id, 'filename must match task_type_id')
            family = match.group(1) if match else ''
            check(family in family_ids, 'work family absent from skill source index')
            check(file.parent.name == family, 'work-family directory mismatch')
            check(isinstance(card['work_family'], str) and card['work_family'].startswith(family + ' '), 'work_family mismatch')
            for field in ['title', 'role', 'trigger', 'expert_time_estimate', 'notes']:
                check(nonempty(card[field]), f'{field} must be nonempty')
            steps = card['workflow_steps']
            check(isinstance(steps, list) and len(steps) >= 3 and all(map(nonempty, steps)), 'workflow_steps must describe multiple nonempty actions')
            for field, keys in [
                ('software', ['name', 'use', 'provision']),
                ('deliverables', ['file', 'form']),
                ('input_data', ['kind', 'point_in_time', 'source_hint']),
            ]:
                items = card[field]
                check(isinstance(items, list) and bool(items), f'{field} must be a nonempty list')
                for item in items if isinstance(items, list) else []:
                    check(isinstance(item, dict) and all(nonempty(item.get(key)) for key in keys), f'{field} requires {keys}')
                    if not isinstance(item, dict):
                        continue
                    if field == 'software':
                        check(item.get('provision') in {'container','mcp','cua','input-data'}, 'unsupported provision')
                    if field == 'input_data':
                        for source_id in re.findall(r'\bS\d{2}\b', item.get('source_hint', '')):
                            check(source_id in source_ids, f'unknown resource {source_id}')
                    if field == 'deliverables' and isinstance(item.get('file'), str):
                        name = PurePosixPath(item['file'])
                        check(not name.is_absolute() and '..' not in name.parts, 'deliverable path must be relative and contained')
            filenames = [item.get('file') for item in card['deliverables'] if isinstance(item, dict)] if isinstance(card['deliverables'], list) else []
            check(len(filenames) == len(set(filenames)), 'duplicate deliverable filename')
            verification = card['verification']
            check(isinstance(verification, dict), 'verification must be a mapping')
            for field in ['profession_checks', 'objective_parts', 'rubric_parts']:
                entries = verification.get(field) if isinstance(verification, dict) else None
                check(isinstance(entries, list) and bool(entries) and all(map(nonempty, entries)), f'verification.{field} must be nonempty')
            evidence = card['evidence']
            check(isinstance(evidence, list) and bool(evidence), 'evidence must be nonempty')
            full_origins, software_evidence = set(), []
            for item in evidence if isinstance(evidence, list) else []:
                check(isinstance(item, dict), 'evidence must be mappings')
                if not isinstance(item, dict):
                    continue
                check(all(nonempty(item.get(key)) for key in ['id','type','origin','url','locator','excerpt','access','checked_at']), 'evidence metadata incomplete')
                parsed = urlsplit(item.get('url', ''))
                check(parsed.scheme in {'http','https'} and bool(parsed.netloc), 'evidence URL must be absolute HTTP(S)')
                try:
                    date.fromisoformat(item.get('checked_at', ''))
                except (ValueError, TypeError):
                    check(False, 'checked_at must be an ISO date string')
                support = item.get('supports')
                check(isinstance(support, list) and bool(support) and set(support) <= SUPPORTS, 'unsupported or absent evidence support tags')
                if item.get('access') in FULL_TEXT and isinstance(support, list):
                    if 'workflow_steps' in support:
                        full_origins.add(item.get('origin'))
                    if 'software' in support:
                        software_evidence.append(item.get('id'))
                evidence_id = item.get('id')
                if evidence_id in evidence_registry:
                    check(evidence_registry[evidence_id] == item, f'inconsistent reused evidence ID {evidence_id}')
                else:
                    evidence_registry[evidence_id] = item
            status = card['status']
            check(status in {'candidate','verified','instantiated'}, 'unsupported status')
            check(isinstance(card['instantiated_tasks'], list), 'instantiated_tasks must be a list')
            if status in {'verified','instantiated'}:
                check(len(full_origins) >= 2, 'verified cards need full-text workflow evidence from two original sources')
                check(bool(software_evidence), 'verified cards need direct full-text software evidence')
                check(any(isinstance(item, dict) and item.get('provision') in {'container','mcp','cua'} for item in card['software']), 'verified cards need a working software provision route')
            if status == 'instantiated':
                check(bool(card['instantiated_tasks']), 'instantiated status requires task IDs')
            elif card['instantiated_tasks']:
                check(False, 'cards with instantiated_tasks must use instantiated status')
            for task_id in card['instantiated_tasks']:
                check(nonempty(task_id) and (ROOT/'tasks'/task_id/'task.toml').is_file(), f'missing instantiated task {task_id}')
            check(isinstance(card['fusable_with'], list), 'fusable_with must be a list')
            cards[card_id], paths[card_id] = card, relative
            fingerprints[card_id] = hashlib.sha256(file.read_bytes()).hexdigest()
    for card_id, card in cards.items():
        for link in card['fusable_with'] if isinstance(card['fusable_with'], list) else []:
            if not isinstance(link, dict) or not all(nonempty(link.get(key)) for key in ['id','relation','note']):
                errors.append(f'{paths[card_id]}: invalid fusion link')
                continue
            if link['id'] not in cards or link['id'] == card_id:
                errors.append(f'{paths[card_id]}: unresolved or self fusion link {link["id"]}')
            if link['relation'] not in {'upstream','downstream','supporting'}:
                errors.append(f'{paths[card_id]}: unsupported fusion relation')
    if not cards:
        errors.append('No active cards found.')
    return {
        'scope': 'Active finance/*/*.yaml and legal/*/*.yaml; excludes _archive.',
        'validation_kind': 'static_structure_and_recorded_evidence_metadata',
        'limitation': 'Does not independently verify source contents, professional quality, elapsed time or software availability.',
        'card_count': len(cards),
        'by_industry': dict(Counter(card['industry'] for card in cards.values())),
        'by_status': dict(Counter(card['status'] for card in cards.values())),
        'evidence_records': len(evidence_registry),
        'card_sha256': fingerprints,
        'errors': errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, default=ROOT/'task-library')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = validate(args.library.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(json.dumps({key:value for key,value in result.items() if key != 'card_sha256'}, ensure_ascii=False))
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
