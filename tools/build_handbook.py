"""Render HANDBOOK.md into a bookmarked, print-ready PDF (ReportLab)."""
import argparse
from pathlib import Path
import re
import textwrap
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted, Flowable, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
ROOT=Path(__file__).resolve().parents[1]
FONTDIR=Path('/usr/share/fonts/truetype/dejavu')
for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONTDIR/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
NAVY=colors.HexColor('#102936');INK=colors.HexColor('#253642');GREEN=colors.HexColor('#087E68');MINT=colors.HexColor('#A6E4C3');PALE=colors.HexColor('#F0F6F7');GRAY=colors.HexColor('#607582');LINE=colors.HexColor('#D7E3E7')
W,H=A4; M=47; WIDTH=W-2*M
styles={
 'body':ParagraphStyle('Body',fontName='Body',fontSize=9.1,leading=13.3,spaceAfter=6.5,textColor=INK,splitLongWords=True),
 'H1':ParagraphStyle('H1',fontName='Bold',fontSize=20,leading=26,textColor=NAVY,spaceAfter=18,keepWithNext=True),
 'H2':ParagraphStyle('H2',fontName='Bold',fontSize=12,leading=17,textColor=GREEN,spaceBefore=13,spaceAfter=7,keepWithNext=True),
 'H3':ParagraphStyle('H3',fontName='Bold',fontSize=10,leading=15,textColor=NAVY,spaceBefore=10,spaceAfter=5,keepWithNext=True),
 'bullet':ParagraphStyle('Bullet',fontName='Body',fontSize=9.1,leading=13.3,spaceAfter=5,leftIndent=11,firstLineIndent=-10,textColor=INK),
 'table':ParagraphStyle('TableCell',fontName='Body',fontSize=7.7,leading=11.2,textColor=INK,spaceAfter=0),
 'th':ParagraphStyle('TableHeader',fontName='Bold',fontSize=7.7,leading=11.2,textColor=colors.white,spaceAfter=0),
 'code':ParagraphStyle('Code',fontName='Mono',fontSize=7.1,leading=10.1,textColor=NAVY,backColor=PALE,borderColor=LINE,borderWidth=.5,borderPadding=9,spaceBefore=5,spaceAfter=12),
 'caption':ParagraphStyle('Caption',fontName='Body',fontSize=8,leading=12,textColor=GRAY,spaceBefore=4,spaceAfter=12),
 'toc':ParagraphStyle('TOCEntry',fontName='Body',fontSize=9.5,leading=14,textColor=INK,spaceBefore=3,leftIndent=0),
}

def inline(value):
    value=escape(value)
    value=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',lambda m:f'<link href="{m.group(2)}" color="#087E68">{m.group(1)}</link>',value)
    value=re.sub(r'`([^`]+)`',r'<font name="Mono" size="8.1">\1</font>',value)
    value=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',value)
    # Bare URLs remain complete, clickable and breakable without changing the target.
    if '<link' not in value:
        value=re.sub(r'(https?://[^\s<]+)',lambda m:f'<link href="{m.group(1)}" color="#087E68">{m.group(1)}</link>',value)
    return value

def arrow(c,x1,y1,x2,y2):
    import math
    c.setStrokeColor(GREEN);c.setLineWidth(1.3);c.line(x1,y1,x2,y2)
    angle=math.atan2(y2-y1,x2-x1);size=5
    p=c.beginPath();p.moveTo(x2,y2);p.lineTo(x2-size*math.cos(angle-.5),y2-size*math.sin(angle-.5));p.lineTo(x2-size*math.cos(angle+.5),y2-size*math.sin(angle+.5));p.close()
    c.setFillColor(GREEN);c.drawPath(p,fill=1,stroke=0)

def box(c,x,y,w,h,title,sub='',dark=False):
    c.setFillColor(NAVY if dark else PALE);c.setStrokeColor(LINE);c.roundRect(x,y,w,h,6,fill=1,stroke=1)
    c.setFillColor(colors.white if dark else NAVY);c.setFont('Bold',9.2);c.drawCentredString(x+w/2,y+h/2+3,title)
    if sub:
        c.setFont('Body',7.3);c.setFillColor(MINT if dark else GRAY);c.drawCentredString(x+w/2,y+h/2-10,sub)

class Diagram(Flowable):
    def __init__(self,kind): super().__init__();self.kind=kind;self.width=WIDTH;self.height=344 if kind=='architecture' else 276
    def draw(self):
        c=self.canv
        if self.kind=='architecture':
            lx=25;rx=310;bw=166;bh=43
            c.setFont('Bold',8);c.setFillColor(GREEN);c.drawString(lx,328,'REQUEST PATH');c.drawString(rx,328,'SECRET DELIVERY')
            for y,title,sub in [(268,'Browser','localhost:8443'),(209,'NGINX','TLS / limits / request ID'),(150,'ModSecurity + CRS','Blocking mode'),(91,'Task API','Authentication / validation'),(32,'PostgreSQL','Persistent task records')]:
                box(c,lx,y,bw,bh,title,sub,dark=title=='Task API')
            for y in [268,209,150,91]:arrow(c,lx+bw/2,y,lx+bw/2,y-16)
            box(c,rx,238,bw,bh,'Vault KV v2','Persistent Raft storage',True)
            box(c,rx,170,bw,bh,'Vault Agent','AppRole / read-only policy')
            box(c,rx,102,bw,bh,'Rendered key file','App mount is read-only')
            arrow(c,rx+bw/2,238,rx+bw/2,213);arrow(c,rx+bw/2,170,rx+bw/2,145)
            arrow(c,rx,123,lx+bw,112)
            c.setFont('Body',7.4);c.setFillColor(GRAY);c.drawString(rx,77,'No Vault root token in the API.')
            c.drawString(rx,64,'Cached key survives a Vault outage.')
        else:
            lx=20;rx=300;bw=180;bh=42
            c.setFont('Bold',8);c.setFillColor(GREEN);c.drawString(lx,262,'METRICS / PULL');c.drawString(rx,262,'LOGS / FILE INGESTION')
            for y,title,sub in [(196,'API + HTTPS probe','Counters / histogram / readiness'),(124,'Prometheus','Scrape / evaluate rules'),(52,'Grafana + Alertmanager','Inspect / display alerts')]:box(c,lx,y,bw,bh,title,sub,dark=y==124)
            for y in [196,124]:arrow(c,lx+bw/2,y,lx+bw/2,y-30)
            for y,title,sub in [(196,'API + NGINX','Sanitized JSON log files'),(124,'Logstash','File offsets / persistent queue'),(52,'Elasticsearch + Kibana','Index / search / investigate')]:box(c,rx,y,bw,bh,title,sub,dark=y==124)
            for y in [196,124]:arrow(c,rx+bw/2,y,rx+bw/2,y-30)
            c.setFont('Body',8);c.setFillColor(GRAY);c.drawCentredString(WIDTH/2,17,'Two paths, different questions. No Docker socket mounted.')

class Book(BaseDocTemplate):
    def __init__(self,path,**kw):
        super().__init__(path,pagesize=A4,leftMargin=M,rightMargin=M,topMargin=57,bottomMargin=48,title='AtlasOps - DevOps Portfolio Handbook',author='AtlasOps',**kw)
        self.section='AtlasOps / Practical handbook'
        frame=Frame(M,48,WIDTH,H-105,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='normal',frames=[frame],onPage=self.page))
    def page(self,c,doc):
        c.saveState()
        if doc.page==1:
            c.setFillColor(NAVY);c.rect(0,0,W,H,fill=1,stroke=0)
            c.setFillColor(MINT);c.setFont('Bold',11);c.drawString(M,H-75,'ATLASOPS / PORTFOLIO SERIES')
            c.setFillColor(colors.white);c.setFont('Bold',47);c.drawString(M,H-195,'AtlasOps')
            c.setFont('Bold',25);c.drawString(M,H-242,'DevOps Portfolio')
            c.setFont('Body',19);c.drawString(M,H-273,'Build and Operations Handbook')
            c.setStrokeColor(MINT);c.setLineWidth(3);c.line(M,H-307,M+78,H-307)
            c.setFont('Body',13)
            for i,line in enumerate(['From containers to secure delivery,','observability and recovery.']):c.drawString(M,H-347-i*21,line)
            c.setFillColor(MINT);c.setFont('Body',10)
            for i,line in enumerate(['Docker / NGINX / ModSecurity / Vault','Prometheus / Grafana / Elasticsearch / Logstash / Kibana','CI/CD / Terraform / Ansible / Kubernetes']):c.drawString(M,H-433-i*20,line)
            c.setFillColor(colors.HexColor('#213E4C'));c.roundRect(M,128,WIDTH,112,9,fill=1,stroke=0)
            c.setFillColor(colors.white);c.setFont('Bold',11);c.drawString(M+17,215,'DESIGNED FOR A DEVOPS INTERNSHIP PORTFOLIO')
            c.setFont('Body',9.5)
            for i,line in enumerate(['Moroccan hiring evidence + a complete source project','18 chapters / practical runbooks / test evidence / CV guidance','Prepared for Mohammed Abid / 5 November 2026']):c.drawString(M+17,190-i*19,line)
            c.setFillColor(MINT);c.setFont('Body',8.7);c.drawString(M,76,'Local-first learning lab. Runtime verification boundaries are explicit.')
        else:
            c.setFillColor(GREEN);c.rect(M,H-32,26,3,fill=1,stroke=0)
            c.setFont('Bold',7.6);c.setFillColor(GRAY);c.drawString(M+36,H-32,'ATLASOPS  /  BUILD + OPERATE')
            c.setStrokeColor(LINE);c.setLineWidth(.5);c.line(M,35,W-M,35)
            c.setFont('Body',7.2);c.drawString(M,22,'DevOps portfolio handbook  |  Research checked 5 November 2026')
            c.drawRightString(W-M,22,str(doc.page))
        c.restoreState()
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='H1':
            text=flowable.getPlainText(); key=getattr(flowable,'bookmark',None)
            if key:
                self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,0,False)
                self.notify('TOCEntry',(0,text,self.page,key))

def table(rows):
    n=len(rows[0]);weights={2:[.33,.67],3:[.24,.40,.36],4:[.10,.25,.37,.28]}.get(n,[1/n]*n)
    if n==4 and rows[0][0] not in ['ID','Id']:weights=[.19,.28,.28,.25]
    data=[]
    for i,row in enumerate(rows):
        data.append([Paragraph(inline(cell.strip()),styles['th' if i==0 else 'table']) for cell in row])
    t=Table(data,colWidths=[WIDTH*x for x in weights],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,colors.white]),('LINEBELOW',(0,0),(-1,0),.5,NAVY),('LINEBELOW',(0,1),(-1,-1),.35,LINE)]))
    return t

def parse_markdown(md):
    story=[];lines=md.splitlines();i=0;chapter_count=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            i+=1;code=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                # Wrapping affects only print layout; source files retain exact commands.
                raw=lines[i].replace('\t','    ')
                code.extend(textwrap.wrap(raw,width=92,replace_whitespace=False,drop_whitespace=False,break_long_words=True,break_on_hyphens=False) or [''])
                i+=1
            i+=1
            if len(code)>42:
                for j in range(0,len(code),32):story.append(Preformatted('\n'.join(code[j:j+32]),styles['code']))
            else:story.append(Preformatted('\n'.join(code),styles['code']))
            continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[s.strip() for s in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\s-]+',cell or '-') for cell in row):rows.append(row)
                i+=1
            story += [table(rows),Spacer(1,10)];continue
        if line=='[[ARCHITECTURE]]':
            story += [Diagram('architecture'),Paragraph('Figure 1. Request processing and the independent secret-delivery path.',styles['caption'])];i+=1;continue
        if line=='[[TELEMETRY]]':
            story += [Diagram('telemetry'),Paragraph('Figure 2. Metrics and logs answer different operational questions.',styles['caption'])];i+=1;continue
        if line.startswith('# '):
            if chapter_count:story.append(PageBreak())
            chapter_count+=1
            p=Paragraph(inline(line[2:]),styles['H1']);p.bookmark='chapter-'+str(chapter_count);story.append(p);i+=1;continue
        if line.startswith('## '):story.append(Paragraph(inline(line[3:]),styles['H2']));i+=1;continue
        if line.startswith('### '):story.append(Paragraph(inline(line[4:]),styles['H3']));i+=1;continue
        if line.startswith('- ') or re.match(r'^\d+\. ',line):
            if line.startswith('- '):text='• '+line[2:]
            else:text=line
            story.append(Paragraph(inline(text),styles['bullet']));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|- |\d+\. |\[\[)',lines[i].strip()):
            para.append(lines[i].strip());i+=1
        story.append(Paragraph(inline(' '.join(para)),styles['body']))
    return story

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'docs/AtlasOps_DevOps_Handbook.pdf');args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    doc=Book(str(args.output))
    story=[Spacer(1,1),PageBreak(),Paragraph('Contents',styles['H1']),Paragraph('Use the clickable chapters or PDF bookmarks to move between explanations, operations and evidence.',styles['body'])]
    toc=TableOfContents();toc.levelStyles=[styles['toc']];story.extend([toc,Spacer(1,20),Paragraph('Reading route',styles['H2']),Paragraph('Start with Chapters 1-5, run the monitoring profile, then study one subsystem at a time. Chapter 12 is the operational reference. Chapter 14 states what was verified. Chapter 15 helps you turn the work into an honest portfolio story.',styles['body']),PageBreak()])
    md=(ROOT/'docs/HANDBOOK.md').read_text().replace('\u2011','-').replace('\u2013','-').replace('\u2014',' - ').replace('\u00a0',' ')
    story+=parse_markdown(md)
    doc.multiBuild(story)
    print(args.output)
if __name__=='__main__':main()
