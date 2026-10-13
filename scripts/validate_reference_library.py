#!/usr/bin/env python3
"""Validate a frozen acquisition batch against originals, cards and input views."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def validate(batch):
    errors = []
    records = [json.loads(x) for x in (batch/'catalog.jsonl').read_text().splitlines()]
    docs = {r['document_id']: r for r in records}
    cards = json.loads((batch/'task-card-snapshot.json').read_text())
    card_ids = {c['task_type_id'] for c in cards}
    quality = {q['document_id']: q for q in
               [json.loads(x) for x in (batch/'quality.jsonl').read_text().splitlines()]}
    coverage = json.loads((batch/'input-coverage.json').read_text())
    check = lambda condition, message: None if condition else errors.append(message)
    check(len(docs) == len(records), 'Duplicate document IDs')
    check(set(docs) == set(quality), 'Quality records do not match catalog')
    hashes = []
    for card in cards:
        file = ROOT/card['card_path']
        check(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == card['card_sha256'],
              f"Reviewed card changed: {card['task_type_id']}")
        found = [x['requirement_index'] for x in coverage if x['task_type_id'] == card['task_type_id']]
        check(sorted(found) == list(range(1, len(card['input_data'])+1)),
              f"Coverage missing or duplicated: {card['task_type_id']}")
    for record in records:
        id = record['document_id']
        for key in ['source_id','title','publisher','published_at','content_role','package_id','rights_status']:
            check(bool(record.get(key)), f'{id}: missing {key}')
        for key in ['original_url','publication_url']:
            check(urlparse(record[key]).scheme in {'https','http'}, f'{id}: invalid {key}')
        check(set(record['task_type_ids']) <= card_ids, f'{id}: unknown task type')
        check('2025-07' <= record['published_at'] <= '2026-10-13', f'{id}: outside publication window')
        if record.get('version_of'):
            check(record['version_of'] in docs, f'{id}: unresolved previous version')
            if record['version_of'] in docs:
                check(docs[record['version_of']]['published_at'] <= record['published_at'], f'{id}: reversed version dates')
        if record['acquisition_status'] == 'downloaded':
            path = (ROOT/record['file_path']).resolve()
            check(path.is_relative_to(ROOT/'reference-library'), f'{id}: unsafe file path')
            check(path.is_file(), f'{id}: missing original')
            if path.is_file():
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                check(actual == record['content_hash'], f'{id}: original hash mismatch')
                check(path.stat().st_size == record['bytes'], f'{id}: size mismatch')
                hashes.append(actual)
            check((ROOT/record['parsed_path']/'pages.json').is_file(), f'{id}: missing parsed layer')
            if quality[id].get('ocr_pages_retained'):
                pages = json.loads((ROOT/record['parsed_path']/'ocr-pages.json').read_text())
                check(len(pages) == quality[id]['ocr_pages_retained'], f'{id}: OCR count mismatch')
                check(all(p.get('lines') for p in pages), f'{id}: empty OCR observations')
                check(all(p['original_hash'] == record['content_hash'] for p in pages), f'{id}: OCR source mismatch')
        else:
            check(record['acquisition_status'] == 'link_only' and not record.get('file_path'),
                  f'{id}: failed or miscounted acquisition')
    for row in coverage:
        check(row['task_type_id'] in card_ids, 'Unknown coverage card')
        check(set(row['document_ids']) <= set(docs), 'Unknown coverage document')
        check(bool(row['gap']) and not row['benchmark_ready'], 'Incomplete public inputs labelled ready')
    packages = []
    for file in sorted((ROOT/'reference-library/packages').glob('*/manifest.json')):
        package = json.loads(file.read_text())
        packages.append(package)
        check(set(package['document_ids']) <= set(docs), f'{file}: unknown material')
        check(not package['benchmark_ready'], f'{file}: unjustified workflow readiness')
        for id in package['default_input_document_ids']:
            if id not in docs:
                errors.append(f'{file}: unknown default input {id}')
                continue
            record = docs[id]
            check(record['published_at'] <= package['as_of'], f'{file}: future input {id}')
            check(record['acquisition_status'] == 'downloaded', f'{file}: link-only default input')
            check('answer_bearing' not in record['content_role'], f'{file}: answer-bearing default input {id}')
    for sample in json.loads((batch/'numeric-spot-checks.json').read_text()):
        check(sample['visual_verified'] and sample['matches_extraction'], 'Unresolved numeric spot check')
    report = json.loads((batch/'report.json').read_text())
    check(report['downloaded_originals'] == len(hashes), 'Original count inconsistent')
    check(report['unique_original_hashes'] == len(set(hashes)), 'Hash deduplication inconsistent')
    return {'validation_kind':'original_integrity_card_mapping_version_and_time_views',
            'documents':len(records),'originals':len(hashes),'unique_original_hashes':len(set(hashes)),
            'card_count':len(cards),'input_requirements':len(coverage),'packages':len(packages),
            'scope_limit':'Not a complete professional task trial, redistribution licence, or zero-contamination certification.',
            'errors':errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = validate(args.batch.resolve())
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
