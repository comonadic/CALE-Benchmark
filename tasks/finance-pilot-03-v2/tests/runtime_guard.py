"""Trusted separate-grader prerequisites checked before any submission score."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,traceback
from pathlib import Path
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-dir',default='/workspace/input-data');parser.add_argument('--log-dir',default='/logs/verifier');args=parser.parse_args()
    tests=Path(__file__).resolve().parent;inputs=Path(args.input_dir);logs=Path(args.log_dir);logs.mkdir(parents=True,exist_ok=True)
    report={'status':'invalid','verifier_failed':True,'grading_complete':False,'scope':'trusted grader preconditions; never a candidate score'}
    try:
        manifest=json.loads((tests/'asset-manifest.json').read_text())
        for relative,expected in manifest['trusted_files'].items():
            actual=digest(tests/relative)
            if actual!=expected:raise RuntimeError('Trusted code/context SHA mismatch: '+relative)
        actual_names={p.name for p in inputs.iterdir() if p.is_file()}
        if actual_names!=set(manifest['input_sha256']):raise RuntimeError('Trusted input file set differs: '+str(sorted(actual_names)))
        for name,expected in manifest['input_sha256'].items():
            if digest(inputs/name)!=expected:raise RuntimeError('Trusted input SHA mismatch: '+name)
        for module in ['verify','rubric_bridge','candidate_guard']:
            spec=importlib.util.spec_from_file_location('trusted_'+module,tests/(module+'.py'));loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
        from pypdf import PdfReader
        if len(PdfReader(inputs/'F025-2025-annual-report.pdf').pages)!=99:raise RuntimeError('Trusted official PDF page count changed')
        binaries={}
        for name,override,argument in [('soffice','SOFFICE_BIN','--version'),('pdftoppm','PDFTOPPM_BIN','-v')]:
            executable=os.environ.get(override) or shutil.which(name)
            if not executable:raise RuntimeError('Required native binary missing: '+name)
            process=subprocess.run([executable,argument],capture_output=True,text=True,timeout=30)
            if process.returncode:raise RuntimeError('Required native binary failed: '+name+' '+process.stderr[-500:])
            binaries[name]={'path':executable,'version':(process.stdout+process.stderr).strip()[:400]}
        report={'status':'passed','verifier_failed':False,'scope':'trusted code/source/import/native dependency preflight only; no candidate or professional score','input_sha256':manifest['input_sha256'],'native_binaries':binaries}
    except Exception as exc:
        report.update(error=str(exc),traceback=traceback.format_exc())
        for filename in ['reward.txt','reward.json']:(logs/filename).unlink(missing_ok=True)
        (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (logs/'runtime-guard-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return 0 if report['status']=='passed' else 2
if __name__=='__main__':raise SystemExit(main())
