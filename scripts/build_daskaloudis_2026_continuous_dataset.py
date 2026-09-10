from __future__ import annotations

import argparse
import csv
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

XML='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'; PREL='http://schemas.openxmlformats.org/package/2006/relationships'
SHEET='Table'; DATA_DOI='10.17632/r84yctsxx6.1'; PAPER_DOI='10.30955/gnc2025.00357'
COLS=("phase","time","Q_L_d","OL_g_VS","OLR","HRT","TS_in_gTS_L","TS_out_gTS_L","TS_removal_pct","VS_in_gVS_L","VS_out_gVS_L","VS_removal_pct","pH_in_primary","pH_reactor","alkalinity_mg_CaCO3_L","pH_in_secondary","pH_out","biogas","methane_pct","CH4_L_d","SMP_L_CH4_gVS","methane_yield_Nml_gVS","sCOD_in_gO2_L","COD_out","COD_removal_pct","phenols_in_gGAeq_L","phenols_out_gGAeq_L","phenols_removal_pct","TAN_in","TAN_out")
def colnum(ref):
    n=0
    for ch in ''.join(x for x in ref if x.isalpha()).upper(): n=n*26+ord(ch)-64
    return n
def shared(z):
    try:r=ET.fromstring(z.read('xl/sharedStrings.xml'))
    except KeyError:return []
    return [''.join(n.text or '' for n in it.iter(f'{{{XML}}}t')) for it in r]
def sheetpath(z):
    wb=ET.fromstring(z.read('xl/workbook.xml')); rid=None
    for s in wb.iter(f'{{{XML}}}sheet'):
        if s.attrib['name']==SHEET: rid=s.attrib[f'{{{REL}}}id']; break
    rs=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    for r in rs.iter(f'{{{PREL}}}Relationship'):
        if r.attrib['Id']==rid:
            t=r.attrib['Target'].lstrip('/'); return t if t.startswith('xl/') else 'xl/'+t
    raise ValueError('sheet not found')
def read_rows(p):
    with zipfile.ZipFile(p) as z:
        ss=shared(z); root=ET.fromstring(z.read(sheetpath(z)))
    rows={}
    for c in root.iter(f'{{{XML}}}c'):
        ref=c.attrib['r']; rn=int(''.join(x for x in ref if x.isdigit())); cn=colnum(ref); val=None
        if c.attrib.get('t')=='inlineStr':
            ins=c.find(f'{{{XML}}}is'); val=''.join(n.text or '' for n in ins.iter(f'{{{XML}}}t')) if ins is not None else None
        else:
            v=c.find(f'{{{XML}}}v')
            if v is not None and v.text is not None:
                raw=v.text
                if c.attrib.get('t')=='s': val=ss[int(raw)]
                else:
                    try: val=float(raw)
                    except (TypeError, ValueError): val=raw
        if val=='': val=None
        if val is not None: rows.setdefault(rn,{})[cn]=val
    out=[]
    for rn in sorted(rows):
        if rn<5 or rows[rn].get(2) is None: continue
        rec={'source_row':rn}
        for i,name in enumerate(COLS,1): rec[name]=rows[rn].get(i)
        out.append(rec)
    return out
def same(a,b):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-9)
    return a==b
def coalesce(records):
    groups={}
    for r in records: groups.setdefault(float(r['time']),[]).append(r)
    out=[]
    for t,g in sorted(groups.items()):
        m={}; conflicts=[]
        for c in COLS:
            vals=[]
            for r in g:
                v=r.get(c)
                if v is not None and not any(same(v,x) for x in vals): vals.append(v)
            if len(vals)>1: conflicts.append(c)
            m[c]=vals[0] if len(vals)==1 else None
        if conflicts: raise ValueError(f'conflicting duplicate at day {t}: {conflicts}')
        phase=str(m.get('phase') or '')
        status='unresolved' if phase in {'phase I','phase II','phase III'} else ('biochar_period_supported_by_paper' if phase=='phase IV' else ('start_up' if phase=='start-up' else 'unknown'))
        m.update(study_id='daskaloudis_2026_mendeley',reactor_id='pilot_180L_single_reactor',source_sheet=SHEET,source_rows=';'.join(f'{SHEET}!{r["source_row"]}' for r in g),source_record_count=len(g),qc_flags='coalesced_complementary_duplicate' if len(g)>1 else '',phase_intervention_status=status,source_data_doi=DATA_DOI,associated_paper_doi=PAPER_DOI)
        out.append(m)
    return out
def write(records,out,report):
    meta=("study_id","reactor_id","source_sheet","source_rows","source_record_count","qc_flags","phase_intervention_status","source_data_doi","associated_paper_doi")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=(*meta,*COLS),lineterminator='\n'); w.writeheader(); w.writerows(records)
    rep={'valid':True,'rows_after_coalescing':len(records),'time_min_day':min(float(r['time']) for r in records),'time_max_day':max(float(r['time']) for r in records),'coalesced_duplicate_days':[float(r['time']) for r in records if int(r['source_record_count'])>1],'zero_counts':{},'missing_counts':{},'notes':['No global zero-to-missing conversion applied.','Duplicate days coalesced only when overlapping non-null values agree.','Phase I-III intervention meanings unresolved.','Duplicated pH-in labels and TAN source-unit interpretation remain source metadata issues.']}
    for c in COLS[1:]:
        vals=[r.get(c) for r in records]; rep['zero_counts'][c]=sum(isinstance(v,(int,float)) and float(v)==0 for v in vals if v is not None); rep['missing_counts'][c]=sum(v is None for v in vals)
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(rep,indent=2,sort_keys=True)+'\n')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source_xlsx',type=Path); ap.add_argument('--output',type=Path,default=Path('data/experimental/daskaloudis_2026_continuous_qc.csv')); ap.add_argument('--qc-report',type=Path,default=Path('results/daskaloudis_2026_continuous_qc.json')); a=ap.parse_args(); write(coalesce(read_rows(a.source_xlsx)),a.output,a.qc_report)
if __name__=='__main__': main()
