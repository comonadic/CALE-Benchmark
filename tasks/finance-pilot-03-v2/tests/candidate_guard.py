"""Only known native candidate-file parse defects become ordinary submission0."""
import argparse,json,zipfile
from pathlib import Path
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError
KNOWN_PARSE_DEFECTS=(zipfile.BadZipFile,InvalidFileException,PackageNotFoundError,XMLSyntaxError,KeyError,ValueError)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',default='/workspace/output');parser.add_argument('--log-dir',default='/logs/verifier');args=parser.parse_args()
    output=Path(args.output_dir);logs=Path(args.log_dir);logs.mkdir(parents=True,exist_ok=True)
    defect=None
    # Catch known file-structure exceptions only around native file-opening APIs.
    try:
        workbook=openpyxl.load_workbook(output/'distribution-model.xlsx',data_only=False);workbook.close()
    except KNOWN_PARSE_DEFECTS as exc:defect=('distribution-model.xlsx',type(exc).__name__,str(exc))
    if defect is None:
        try:Document(output/'distribution-note.docx')
        except KNOWN_PARSE_DEFECTS as exc:defect=('distribution-note.docx',type(exc).__name__,str(exc))
    if defect is not None:
        report={'status':'completed','submission_status':'invalid_submission','grading_complete':True,'reward':0,'professional_points':None,'candidate_file':defect[0],'known_parse_defect':defect[1],'candidate_failure_reason':defect[2]}
        (logs/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(logs/'reward.txt').write_text('0\n');(logs/'reward.json').write_text(json.dumps({'reward':0})+'\n')
        return 3
    (logs/'candidate-readability-report.json').write_text(json.dumps({'status':'passed','scope':'native file readability only; no financial score'})+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
