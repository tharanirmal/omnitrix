"""Build the 9-slide Omnitrix pitch deck on docs/engram_template_8.pptx (stdlib only).

    python3 docs/build_pitch_deck.py            # writes docs/Omnitrix-pitch.pptx

Keeps the template's look exactly: black background with its grey/white blob art, Calibri, two-tone titles
(A0A0A0 + FFFFFF), cards 0E0E0E with a 2C2C2C border, greys A0A0A0 / 5A5A5A / E6E6E6, and one accent, amber F5B301.
Content and numbers follow docs/deck-prompt-claude-max.md; speaker notes are in docs/pitch-notes.md.
Diagrams are native vector shapes (editable in PowerPoint); the two charts are native, editable charts.
"""
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "engram_template_8.pptx"
SHOTS = ROOT / "Claude outputs"
OUT = ROOT / "docs" / "Omnitrix-pitch.pptx"

EMU = 914400
W, H = 12191695, 6858000
SW = W / EMU
BLACK, CARD, BORDER, GREY, DIM, LIGHT, WHITE, AMBER = ("000000", "0E0E0E", "2C2C2C", "A0A0A0", "5A5A5A", "E6E6E6",
                                                       "FFFFFF", "F5B301")
FOOTER = "Omnitrix  ·  MSRIT Hackathon  ·  Track 1 Sovereign AI"
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def e(inches):
    return int(round(inches * EMU))


def run(t, s, c, b=False, i=False):
    return (f'<a:r><a:rPr lang="en-US" sz="{int(s * 100)}" b="{int(b)}" i="{int(i)}" dirty="0"><a:solidFill>'
            f'<a:srgbClr val="{c}"/></a:solidFill><a:latin typeface="Calibri"/><a:cs typeface="Calibri"/></a:rPr>'
            f'<a:t xml:space="preserve">{escape(t)}</a:t></a:r>')


class Slide:
    def __init__(self, n, bg):
        self.n, self.shapes, self.rels, self.next_id = n, [], [], 1
        self.rel("slideLayout", "../slideLayouts/slideLayout7.xml")
        self.pic("background", f"../media/{bg}", 0, 0, SW, H / EMU)

    def rel(self, kind, target):
        rid = f"rId{len(self.rels) + 1}"
        self.rels.append((rid, kind, target))
        return rid

    def nid(self):
        self.next_id += 1
        return self.next_id

    def _sp(self, geom, x, y, w, h, fill, line, lw, dash=None, adj=None, rot=0, flip=""):
        i = self.nid()
        fill_x = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        dash_x = f'<a:prstDash val="{dash}"/>' if dash else ""
        line_x = (f'<a:ln w="{lw}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill>{dash_x}</a:ln>'
                  if line else "<a:ln><a:noFill/></a:ln>")
        av = f'<a:gd name="adj" fmla="val {adj}"/>' if adj is not None else ""
        rot_x = f' rot="{int(rot * 60000)}"' if rot else ""
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm{rot_x}{flip}><a:off x="{e(x)}" y="{e(y)}"/><a:ext cx="{e(w)}" cy="{e(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="{geom}"><a:avLst>{av}</a:avLst></a:prstGeom>{fill_x}{line_x}</p:spPr>'
            f'<p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p>'
            f'</p:txBody></p:sp>')

    def box(self, x, y, w, h, fill=CARD, line=BORDER, lw=12700, adj=6000, dash=None):
        self._sp("roundRect", x, y, w, h, fill, line, lw, dash, adj)

    def shape(self, geom, x, y, w, h, fill=None, line=AMBER, lw=19050):
        self._sp(geom, x, y, w, h, fill, line, lw)

    def text(self, x, y, w, h, paras, anchor="t", align="l", after=0):
        """paras: list of paragraphs; each is a list of runs (text, size, color[, bold[, italic]])."""
        i = self.nid()
        body = "".join(
            f'<a:p><a:pPr algn="{align}"><a:spcAft><a:spcPts val="{int(after * 100)}"/></a:spcAft></a:pPr>'
            + "".join(run(*r) for r in p) + "</a:p>" for p in paras)
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="TextBox {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{e(x)}" y="{e(y)}"/><a:ext cx="{e(w)}" cy="{e(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" rIns="0" tIns="0" bIns="0" anchor="{anchor}">'
            f'<a:normAutofit/></a:bodyPr><a:lstStyle/>{body}</p:txBody></p:sp>')

    def t(self, x, y, w, h, s, size=14, color=LIGHT, bold=False, align="l", anchor="t", italic=False):
        self.text(x, y, w, h, [[(s, size, color, bold, italic)]], anchor=anchor, align=align)

    def pic(self, name, target, x, y, w, h, frame=False, crop=None):
        i = self.nid()
        rid = self.rel("image", target)
        geom = ('<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 2500"/></a:avLst></a:prstGeom>'
                if frame else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>')
        line = f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{BORDER}"/></a:solidFill></a:ln>' if frame else ""
        src = ('<a:srcRect ' + " ".join(f'{k}="{int(v * 100000)}"' for k, v in crop.items()) + "/>") if crop else ""
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="{escape(name)}" descr="{escape(name)}"/><p:cNvPicPr>'
            f'<a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{rid}"/>'
            f'{src}<a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{e(x)}" y="{e(y)}"/>'
            f'<a:ext cx="{e(w)}" cy="{e(h)}"/></a:xfrm>{geom}{line}</p:spPr></p:pic>')

    def line(self, x1, y1, x2, y2, color=GREY, arrow=True, lw=15875, dash=None):
        i = self.nid()
        flip = (' flipH="1"' if x2 < x1 else "") + (' flipV="1"' if y2 < y1 else "")
        head = '<a:tailEnd type="triangle" w="med" len="med"/>' if arrow else ""
        dash_x = f'<a:prstDash val="{dash}"/>' if dash else ""
        self.shapes.append(
            f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{i}" name="Line {i}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
            f'<p:spPr><a:xfrm{flip}><a:off x="{e(min(x1, x2))}" y="{e(min(y1, y2))}"/>'
            f'<a:ext cx="{e(abs(x2 - x1))}" cy="{e(abs(y2 - y1))}"/></a:xfrm><a:prstGeom prst="straightConnector1">'
            f'<a:avLst/></a:prstGeom><a:ln w="{lw}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{dash_x}'
            f'{head}</a:ln></p:spPr></p:cxnSp>')

    def chart(self, n, x, y, w, h):
        i = self.nid()
        rid = self.rel("chart", f"../charts/chart{n}.xml")
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Chart {i}"/><p:cNvGraphicFramePr/>'
            f'<p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{e(x)}" y="{e(y)}"/><a:ext cx="{e(w)}" cy="{e(h)}"/>'
            f'</p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            f'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" r:id="{rid}"/>'
            f'</a:graphicData></a:graphic></p:graphicFrame>')

    # ------------------------------------------------------------------------------------ template parts
    def title(self, grey, white, size=36, sub=None):
        self.text(0.6, 0.5, SW - 1.2, 0.8, [[(grey, size, GREY), (white, size, WHITE)]], anchor="ctr", align="ctr")
        if sub:
            self.t(1.8, 1.32, SW - 3.6, 0.4, sub, 15, GREY, align="ctr")

    def label(self, x, y, w, s, color=AMBER, align="l"):
        self.t(x, y, w, 0.28, s, 11, color, True, align)

    def badge(self, x, y, s, d=0.5):
        self._sp("ellipse", x, y, d, d, CARD, AMBER, 15875)
        self.t(x, y, d, d, s, 12, AMBER, True, "ctr", "ctr")

    def pill(self, x, y, w, h, s, size=13, color=LIGHT, bold=True, italic=False):
        self.box(x, y, w, h, adj=50000)
        self.t(x, y, w, h, s, size, color, bold, "ctr", "ctr", italic)

    def footer(self):
        self.t(0.6, 7.05, 6.0, 0.25, FOOTER, 9, DIM)
        self.t(11.9, 7.05, 0.85, 0.25, f"{self.n:02d}", 9, DIM, align="r")

    def xml(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<p:sld {A} xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:bg>'
                f'<p:bgPr><a:solidFill><a:srgbClr val="{BLACK}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
                '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                f'<p:grpSpPr/>{"".join(self.shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/>'
                '</p:clrMapOvr></p:sld>')

    def rels_xml(self):
        t = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns='
                '"http://schemas.openxmlformats.org/package/2006/relationships">' +
                "".join(f'<Relationship Id="{i}" Type="{t}{k}" Target="{g}"/>' for i, k, g in self.rels) +
                "</Relationships>")


slides = []
CW = SW - 1.2

# 1 · Intro ---------------------------------------------------------------------------------------------------------
s = Slide(1, "image1.png")
s.label(0.6, 1.95, CW, "SOVEREIGN AI  ·  PERSONAL SECRETARY", align="ctr")
s.text(0.6, 2.25, CW, 1.2, [[("Omni", 66, GREY), ("trix", 66, WHITE)]], anchor="ctr", align="ctr")
s.t(1.5, 3.55, SW - 3.0, 0.5, "A local AI secretary that remembers, plans and acts, only with your OK.", 20, WHITE,
    align="ctr")
pills = [("Brain: engram", 2.2), ("Track 1 · Sovereign AI", 2.6), ("MSRIT Hackathon", 2.2)]
x = (SW - (sum(w for _, w in pills) + 0.6)) / 2
for lab, w in pills:
    s.pill(x, 4.55, w, 0.5, lab, 12)
    x += w + 0.3
slides.append(s)

# 2 · Problem ------------------------------------------------------------------------------------------------------
s = Slide(2, "image1.png")
s.title("Storing is easy. ", "Judging is hard.",
        sub="Your work lives in email, meetings and notes. Today's AI memory tools get the small judgements wrong.")
cards = [("can", "97.8%", "of Mem0 memories were junk", "audit of 10,134 memories"),
         ("noSmoking", "41%", "of Graphiti facts invalidated", "~3,950 facts; 3 of 4 audited were wrong"),
         ("cloud", "7.5%", "of queries leaked private data", "even careful local + cloud (PAPILLON)")]
cw, gap = 3.7, 0.4
x0 = (SW - (3 * cw + 2 * gap)) / 2
for k, (icon, num, lab, src) in enumerate(cards):
    x = x0 + k * (cw + gap)
    s.box(x, 2.1, cw, 3.25)
    s.shape(icon, x + cw / 2 - 0.3, 2.35, 0.6, 0.55)
    s.t(x + 0.2, 3.0, cw - 0.4, 0.9, num, 52, WHITE, True, "ctr", "ctr")
    s.t(x + 0.25, 3.95, cw - 0.5, 0.4, lab, 16, WHITE, True, "ctr")
    s.t(x + 0.3, 4.45, cw - 0.6, 0.6, src, 12, GREY, align="ctr")
s.pill(0.6, 5.75, CW, 0.62, "Remember this?  Did it change?  Should it be sent?  Thousands of small judgements a day.",
       15, LIGHT, False, True)
slides.append(s)

# 3 · Our answer ---------------------------------------------------------------------------------------------------
s = Slide(3, "image3.png")
s.title("Our answer: ", "a personal AI you own")
tiles = [("Personal AI", "learns how you judge"), ("Locally hosted", "zero cloud calls"),
         ("Fine-tuned LLM", "a 1.7B trained on you"), ("Society of LLMs", "fast small, slow large, and you"),
         ("Second brain", "memory with its sources")]
tw = (CW - 4 * 0.2) / 5
for k, (head, sub) in enumerate(tiles):
    x = 0.6 + k * (tw + 0.2)
    s.box(x, 1.55, tw, 1.6)
    s.badge(x + 0.25, 1.75, f"0{k + 1}", 0.48)
    s.t(x + 0.25, 2.33, tw - 0.4, 0.35, head, 15, WHITE, True)
    s.t(x + 0.25, 2.68, tw - 0.4, 0.4, sub, 12, GREY)
tiers = [("S0", "Code"), ("S1", "Small judge"), ("S2", "14B model"), ("H", "You")]
lw_, lg = 1.55, 0.45
lx0 = (SW - (4 * lw_ + 3 * lg)) / 2
for k, (tag, name) in enumerate(tiers):
    x = lx0 + k * (lw_ + lg)
    s.box(x, 3.4, lw_, 0.62, adj=20000, line=AMBER if tag == "S1" else BORDER)
    s.text(x, 3.4, lw_, 0.62, [[(tag + "  ", 12, AMBER, True), (name, 12, WHITE, True)]], anchor="ctr", align="ctr")
    if k < 3:
        s.line(x + lw_ + 0.06, 3.71, x + lw_ + lg - 0.06, 3.71)
iw = 2.35 * 2340 / 844
s.pic("Five views of the app: sign in, database, agents, add data, audit", "../media/views.png",
      (SW - iw) / 2, 4.3, iw, 2.35, frame=True)
slides.append(s)

# 4 · Technical 1: the brain and the society of agents --------------------------------------------------------------
s = Slide(4, "image2.png")
s.title("The brain ", "and its society of agents", 34)
s.box(0.6, 1.45, CW, 5.05, fill=None, line=DIM, lw=15875, adj=2500, dash="dash")
s.label(0.85, 1.58, 6, "YOUR LAPTOP  ·  LOCAL ONLY  ·  ZERO CLOUD CALLS", GREY)
s.box(0.9, 2.0, 2.15, 2.3)
s.t(1.1, 2.15, 1.8, 0.35, "Sources", 15, WHITE, True)
s.text(1.1, 2.6, 1.8, 1.6, [[(t, 12, GREY)] for t in ("Email", "Meetings", "Notes", "Add data")], after=4)
s.box(3.5, 1.9, 5.75, 2.5, line=AMBER, lw=22225)
s.label(3.75, 2.02, 3, "THE BRAIN")
s.t(3.75, 2.3, 3, 0.4, "engram", 20, WHITE, True)
tw = (5.25 - 3 * 0.12) / 4
for k, (tag, name) in enumerate([("S0", "Code"), ("S1", "1.7B judge"), ("S2", "14B model"), ("H", "You")]):
    x = 3.75 + k * (tw + 0.12)
    s.box(x, 2.85, tw, 0.7, fill=BLACK, adj=12000)
    s.text(x, 2.9, tw, 0.6, [[(tag, 11, AMBER, True)], [(name, 12, WHITE, True)]], anchor="ctr", align="ctr")
s.box(3.75, 3.7, 5.25, 0.45, fill=BLACK, adj=20000)
s.t(3.75, 3.7, 5.25, 0.45, "Every judgement  →  one hash-chained ledger", 12, LIGHT, align="ctr", anchor="ctr")
s.box(9.7, 2.0, 2.3, 2.3)
s.t(9.9, 2.15, 2.0, 0.35, "You", 15, WHITE, True)
s.text(9.9, 2.6, 2.0, 1.6, [[(t, 12, GREY)] for t in ("Web app", "Watch (Herald)", "Obsidian vault", "MCP tools")],
       after=4)
s.line(3.08, 3.15, 3.46, 3.15)
s.line(9.28, 3.15, 9.66, 3.15)
s.text(0.6, 4.55, CW, 0.3, [[("7 ROLES ON ONE PIPELINE   ", 11, GREY, True), ("22 planned agents → 7 roles", 11, AMBER, True)]],
       align="ctr")
roles = ["Librarian", "Researcher", "Memory", "Planner", "Operator", "Guardian", "Herald", "Diplomat (demo)"]
rw = (11.53 - 7 * 0.13) / 8
for k, r in enumerate(roles):
    x = 0.9 + k * (rw + 0.13)
    demo = "demo" in r
    s.box(x, 4.95, rw, 0.5, adj=50000, line=DIM if demo else BORDER, dash="dash" if demo else None)
    s.t(x, 4.95, rw, 0.5, r, 12, GREY if demo else WHITE, True, "ctr", "ctr")
s._sp("can", 2.3, 5.68, 0.5, 0.62, CARD, AMBER, 15875)
s.text(3.0, 5.7, 8.0, 0.6, [[("Postgres 17 + pgvector   ", 13, WHITE, True),
                             ("items · chunks · beliefs · judgements · labels · people · plan_entries · herald_cards",
                              12, GREY)]], anchor="ctr")
slides.append(s)

# 5 · Technical 2: fine-tuning and the watch app ------------------------------------------------------------------------
s = Slide(5, "image4.png")
s.title("A judge trained on you, ", "a watch that asks you", 32)
s.label(0.6, 1.45, 5.9, "FINE-TUNING THE LLM")
loop = [("Your behaviour", "replies, filing"), ("Labels", "5,958"), ("LoRA on the Mac", "54 min"),
        ("The judge", "934 MB"), ("The ledger", "every decision")]
nw = (5.95 - 4 * 0.18) / 5
for k, (head, sub) in enumerate(loop):
    x = 0.6 + k * (nw + 0.18)
    s.box(x, 1.85, nw, 0.78, adj=12000, line=AMBER if k == 3 else BORDER)
    s.text(x + 0.05, 1.9, nw - 0.1, 0.68, [[(head, 10.5, WHITE, True)], [(sub, 10, AMBER if k else GREY, True)]],
           anchor="ctr", align="ctr")
    if k < 4:
        s.line(x + nw + 0.02, 2.24, x + nw + 0.16, 2.24)
lx_end, lx_start = 0.6 + 4 * (nw + 0.18) + nw / 2, 0.6 + 1 * (nw + 0.18) + nw / 2
s.line(lx_end, 2.65, lx_end, 2.88, arrow=False)
s.line(lx_end, 2.88, lx_start, 2.88, arrow=False)
s.line(lx_start, 2.88, lx_start, 2.67)
s.t(2.0, 2.93, 3.2, 0.25, "your taps become new labels", 10, GREY, align="ctr", italic=True)
s.t(0.6, 3.3, 5.95, 0.28, "Accuracy on held-out conversations (%)", 11, GREY)
s.chart(1, 0.95, 3.5, 5.75, 3.35)
# the watch
s.label(6.95, 1.45, 5.8, "HERALD  ·  KOTLIN WEAR OS APP")
cx, cy, d = 7.0, 1.95, 2.75
s._sp("ellipse", cx, cy, d, d, CARD, BORDER, 38100)
s.t(cx + 0.4, cy + 0.55, d - 0.8, 0.3, "Approve?", 12, AMBER, True, "ctr")
s.t(cx + 0.35, cy + 0.85, d - 0.7, 0.35, "email.reply_email", 13, WHITE, True, "ctr")
s.t(cx + 0.45, cy + 1.2, d - 0.9, 0.4, "reply “Got it, thank you!” to sofia", 10, GREY, align="ctr")
for k, (lab, col) in enumerate([("Deny", LIGHT), ("Approve", AMBER)]):
    bx = cx + 0.45 + k * 0.97
    s.box(bx, cy + 1.75, 0.88, 0.4, fill=BLACK, line=col, adj=50000)
    s.t(bx, cy + 1.75, 0.88, 0.4, lab, 11, col, True, "ctr", "ctr")
steps = ["The gate pauses an action", "Long-poll over Wi-Fi, no cloud push", "The watch buzzes", "You tap → the ledger"]
for k, st in enumerate(steps):
    y = 1.95 + k * 0.72
    s.box(10.0, y, 2.73, 0.55, adj=15000)
    s.text(10.15, y, 2.5, 0.55, [[(f"{k + 1}  ", 11, AMBER, True), (st, 11, WHITE, True)]], anchor="ctr")
    if k < 3:
        s.line(11.36, y + 0.56, 11.36, y + 0.71)
chips = [("mDNS + HMAC", 1.45), ("19 s pause → tap", 1.6), ("Whisper ~0.5 s", 1.45)]
x = 7.0
for lab, w in chips:
    s.pill(x, 5.0, w, 0.42, lab, 11)
    x += w + 0.14
s.t(7.0, 5.6, 4.4, 0.6, "Galaxy Watch 5 · Wear OS 5 · Kotlin + Compose · direct Wi-Fi to the Mac, no phone app",
    11, GREY)
slides.append(s)

# 6 · Impact and benefits ---------------------------------------------------------------------------------------------
s = Slide(6, "image1.png")
s.title("Impact ", "and benefits")
tiles = [("PRIVATE", "0", "cloud calls: every model and store on your laptop"),
         ("PERSONALISED", "96.6%", "judge trained on you (14B: 95.5%)"),
         ("SIMPLIFIED", "7 roles", "one pipeline, one tap on the watch"),
         ("TIME", "807 → 255 s", "memory gate on 60 emails"),
         ("COST", "934 MB", "judge, 3–5× faster, no API bills"),
         ("ACCURACY", "40.0% → 6.7%", "harmful actions, through the gate")]
tw, th = (8.1 - 2 * 0.25) / 3, 2.2
for k, (lab, big, sub) in enumerate(tiles):
    x, y = 0.6 + (k % 3) * (tw + 0.25), 1.6 + (k // 3) * (th + 0.25)
    s.box(x, y, tw, th)
    s.label(x + 0.25, y + 0.22, tw - 0.5, lab)
    s.t(x + 0.25, y + 0.55, tw - 0.5, 0.8, big, 30 if len(big) <= 11 else 21, WHITE, True, anchor="ctr")
    s.t(x + 0.25, y + 1.42, tw - 0.5, 0.65, sub, 12, GREY)
# TAM / SAM / SOM, nested circles sharing a bottom edge
s.label(9.35, 1.6, 3.0, "MARKET", align="ctr")
cxm, base = 10.85, 5.95
for dd, fill, line in [(3.7, CARD, BORDER), (2.45, CARD, GREY), (1.25, CARD, AMBER)]:
    s._sp("ellipse", cxm - dd / 2, base - dd, dd, dd, fill, line, 19050)
s.text(cxm - 1.3, base - 3.55, 2.6, 0.9, [[("TAM  $3.4B", 15, WHITE, True)],
                                         [("personal AI assistants, 2025", 10, GREY)]], align="ctr")
s.text(cxm - 1.0, base - 2.3, 2.0, 0.9, [[("SAM  ~$340M", 13, WHITE, True)],
                                        [("assumed 10%: privacy-first", 9.5, GREY)]], align="ctr")
s.text(cxm - 0.55, base - 0.95, 1.1, 0.7, [[("SOM", 11, AMBER, True)], [("~$3.4M", 11, WHITE, True)]], align="ctr")
s.t(8.95, 6.05, 3.8, 0.55, "TAM: Research and Markets (2026), $19.63B by 2030. SAM, SOM (1% of SAM in 3 years): our "
    "assumptions.", 9, GREY, align="ctr")
slides.append(s)

# 7 · Feasibility and viability -------------------------------------------------------------------------------------------
s = Slide(7, "image3.png")
s.title("Feasible today, ", "on one laptop")
cols = [(0.6, 3.5), (4.3, 5.1), (9.6, 3.13)]
for x, w in cols:
    s.box(x, 1.55, w, 4.45)
s.label(0.9, 1.8, 3, "COMPUTE")
for k, (big, sub) in enumerate([("24 GB", "one MacBook Pro (M5 Pro)"), ("934 MB", "the 4-bit judge"),
                                ("54 min", "LoRA training, 18 GB peak")]):
    y = 2.25 + k * 1.2
    s.t(0.9, y, 2.9, 0.55, big, 30, WHITE, True)
    s.t(0.9, y + 0.6, 2.9, 0.35, sub, 12, GREY)
s.label(4.6, 1.8, 4, "BRAIN LATENCY  (log scale)")
s.chart(2, 4.4, 2.1, 4.9, 3.8)
s.label(9.9, 1.8, 2.6, "PRIVACY")
s.text(9.9, 2.2, 2.6, 1.6, [[("•  ", 13, AMBER, True), (t, 12.5, LIGHT)] for t in
                             ("Zero cloud calls", "Hash-chained ledger of every decision",
                              "DPDP-ready: 1-year logs, 72-hour breach reports")], after=6)
s.t(9.9, 3.85, 2.6, 0.35, "Penalties up to ₹250 crore", 13, AMBER, True)
s.pic("Sign-in page: served on 127.0.0.1, nothing from the network", "../media/login.png", 9.85, 4.35, 2.63,
      2.63 * 330 / 768, frame=True, crop={"b": 0.5875, "r": 0.4})      # the page's top-left: title and "127.0.0.1"
s.pill(0.6, 6.2, CW, 0.55, "Viable: it runs today on hardware the owner already has.", 14, LIGHT, False, True)
slides.append(s)

# 8 · References --------------------------------------------------------------------------------------------------------
s = Slide(8, "image2.png")
s.title("References ", "we built on")
refs = ["Kim et al., multi-agent scaling across 180 configurations, arXiv:2512.08296",
        "Cemri et al., MAST: why multi-agent systems fail, arXiv:2503.13657",
        "Zheng et al., persona prompts don't improve accuracy, arXiv:2311.10054",
        "NATURAL PLAN, arXiv:2406.04520",
        "Solver-checked LLM planning (10% → 93.9%), arXiv:2404.11891",
        "NVIDIA, Small Language Models are the Future of Agentic AI, arXiv:2506.02153",
        "PAPILLON (NAACL 2025): local + cloud delegation leaks 7.5%",
        "Mem0 memory audit (mem0 #4573); Graphiti invalidation report (graphiti #1728)",
        "India, Digital Personal Data Protection Rules, 2025",
        "Datasets: EnronQA (CC BY 4.0), WorkBench (MIT), QMSum / AMI",
        "Models and tools: Qwen3-1.7B, Qwen3-14B, Whisper large-v3-turbo, MLX, Ollama, PostgreSQL + pgvector, "
        "OR-Tools CP-SAT",
        "Research and Markets, Personal AI Assistant Market Report 2026 (TAM)"]
half = (CW - 0.4) / 2
for c in range(2):
    x = 0.6 + c * (half + 0.4)
    s.box(x, 1.6, half, 4.6)
    s.text(x + 0.4, 1.95, half - 0.8, 4.1,
           [[(f"{c * 6 + k + 1:>2}   ", 14, AMBER, True), (r, 14, LIGHT)] for k, r in enumerate(refs[c * 6:c * 6 + 6])],
           after=14)
slides.append(s)

# 9 · Thank you ---------------------------------------------------------------------------------------------------------
s = Slide(9, "image4.png")
s.pic("flag", "../media/image5.png", SW / 2 - 0.3, 1.55, 0.6, 0.6)
s.text(0.6, 2.35, CW, 1.1, [[("Thank ", 60, GREY), ("you", 60, WHITE)]], anchor="ctr", align="ctr")
s.t(1.5, 3.6, SW - 3.0, 0.5, "Your brain, on your machine.", 20, WHITE, align="ctr")
for k, (big, sub) in enumerate([("github.com/tharanirmal/omnitrix", "Repo"), ("TODO: team contact", "Contact")]):
    w = 4.0
    x = SW / 2 - w - 0.15 + k * (w + 0.3)
    s.box(x, 4.45, w, 1.05, adj=12000)
    s.t(x, 4.58, w, 0.45, big, 16, WHITE, True, "ctr")
    s.t(x, 5.07, w, 0.3, sub, 11, GREY, align="ctr")
slides.append(s)

for sl in slides:
    if sl.n > 1:
        sl.footer()


# ------------------------------------------------------------------------------------------------------------ charts
def chart_xml(cats, series, fmt, horizontal=False, log=False, legend=True, vmax=None):
    cat_ref = f"Sheet1!$A$2:$A${len(cats) + 1}"
    cat = (f'<c:cat><c:strRef><c:f>{cat_ref}</c:f><c:strCache><c:ptCount val="{len(cats)}"/>' +
           "".join(f'<c:pt idx="{i}"><c:v>{escape(c)}</c:v></c:pt>' for i, c in enumerate(cats)) +
           "</c:strCache></c:strRef></c:cat>")
    txt = (lambda sz, c, b=0: f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{sz}" b="{b}">'
           f'<a:solidFill><a:srgbClr val="{c}"/></a:solidFill><a:latin typeface="Calibri"/></a:defRPr></a:pPr>'
           f'<a:endParaRPr lang="en-US"/></a:p></c:txPr>')
    sers = ""
    for k, (name, color, vals) in enumerate(series):
        col = "BCDEFG"[k]
        sers += (f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx><c:strRef><c:f>Sheet1!${col}$1</c:f>'
                 f'<c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>{escape(name)}</c:v></c:pt></c:strCache>'
                 f'</c:strRef></c:tx><c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr>'
                 f'<c:invertIfNegative val="0"/>{cat}<c:val><c:numRef><c:f>Sheet1!${col}$2:${col}${len(cats) + 1}'
                 f'</c:f><c:numCache><c:formatCode>General</c:formatCode><c:ptCount val="{len(vals)}"/>' +
                 "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(vals)) +
                 "</c:numCache></c:numRef></c:val></c:ser>")
    scaling = ('<c:logBase val="10"/>' if log else "") + '<c:orientation val="minMax"/>' + \
        (f'<c:max val="{vmax}"/>' if vmax else "") + ('<c:min val="1"/>' if log else '<c:min val="0"/>')
    leg = (f'<c:legend><c:legendPos val="t"/><c:overlay val="0"/>{txt(1000, LIGHT)}</c:legend>' if legend else "")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        f'{A} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<c:date1904 val="0"/><c:roundedCorners val="0"/><c:chart><c:autoTitleDeleted val="1"/><c:plotArea>'
        f'<c:layout/><c:barChart><c:barDir val="{"bar" if horizontal else "col"}"/><c:grouping val="clustered"/>'
        f'<c:varyColors val="0"/>{sers}<c:dLbls><c:numFmt formatCode="{escape(fmt, {chr(34): "&quot;"})}" '
        f'sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>{txt(1000, LIGHT, 1)}'
        '<c:dLblPos val="outEnd"/><c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/>'
        '<c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>'
        f'<c:gapWidth val="{55 if horizontal else 70}"/><c:overlap val="-8"/><c:axId val="5001"/><c:axId val="5002"/>'
        '</c:barChart><c:catAx><c:axId val="5001"/><c:scaling>'
        f'<c:orientation val="{"maxMin" if horizontal else "minMax"}"/></c:scaling><c:delete val="0"/>'
        f'<c:axPos val="{"l" if horizontal else "b"}"/><c:numFmt formatCode="General" sourceLinked="0"/>'
        '<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:spPr><a:ln><a:solidFill><a:srgbClr val="{BORDER}"/></a:solidFill></a:ln></c:spPr>{txt(1000, LIGHT)}'
        '<c:crossAx val="5002"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/>'
        '<c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx><c:valAx><c:axId val="5002"/>'
        f'<c:scaling>{scaling}</c:scaling><c:delete val="1"/><c:axPos val="{"b" if horizontal else "l"}"/>'
        '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
        '<c:tickLblPos val="nextTo"/><c:crossAx val="5001"/><c:crosses val="autoZero"/>'
        f'<c:crossBetween val="between"/></c:valAx><c:spPr><a:noFill/></c:spPr></c:plotArea>{leg}'
        '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln>'
        '</c:spPr><c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>')


def workbook(template_xlsx, out, cats, series):
    """The sheet behind a chart, so 'Edit Data' in PowerPoint shows the same numbers."""
    with zipfile.ZipFile(template_xlsx) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    strings = list(cats) + [n for n, _, _ in series]
    parts["xl/sharedStrings.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/'
        f'spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">' +
        "".join(f"<si><t>{escape(t)}</t></si>" for t in strings) + "</sst>").encode()
    cols = "BCDEFG"[:len(series)]
    rows = ['<row r="1">' + "".join(f'<c r="{c}1" t="s"><v>{len(cats) + k}</v></c>' for k, c in enumerate(cols)) +
            "</row>"]
    for i in range(len(cats)):
        rows.append(f'<row r="{i + 2}"><c r="A{i + 2}" t="s"><v>{i}</v></c>' +
                    "".join(f'<c r="{c}{i + 2}"><v>{series[k][2][i]}</v></c>' for k, c in enumerate(cols)) + "</row>")
    parts["xl/worksheets/sheet1.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/'
        f'spreadsheetml/2006/main"><dimension ref="A1:{cols[-1]}{len(cats) + 1}"/><sheetData>' + "".join(rows) +
        "</sheetData></worksheet>").encode()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


CHARTS = {
    1: dict(cats=["Supported?", "Relevant?", "Will reply?", "Folder (12)?"],
            series=[("1.7B base", DIM, [83.7, 74.4, 44.6, 31.5]), ("14B zero-shot", GREY, [95.5, 87.5, 55.4, 47.9]),
                    ("1.7B fine-tuned on you", AMBER, [96.6, 90.9, 60.1, 52.7])],
            fmt="0.0", vmax=110),
    2: dict(cats=["Keyword search", "Searchable after add", "Hybrid search", "Small judge, per email",
                  "Whisper, 2.5 s clip", "Answer, draft mode", "Answer, median"],
            series=[("milliseconds", GREY, [1.9, 13, 28, 214, 500, 1700, 11000])],
            fmt='[<10]0.0" ms";[<1000]0" ms";#,##0" ms"', horizontal=True, log=True, legend=False, vmax=100000),
}


# ------------------------------------------------------------------------------------------------------------ package
def build():
    work = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(TEMPLATE) as z:
        z.extractall(work)
    ppt = work / "ppt"
    tmpl_xlsx = ppt / "embeddings/Microsoft_Excel_Sheet1.xlsx"
    xlsx_copy = work / "_template.xlsx"
    shutil.copy(tmpl_xlsx, xlsx_copy)
    for f in list((ppt / "charts").rglob("*")) + [tmpl_xlsx]:
        if f.is_file():
            f.unlink()
    for n, spec in CHARTS.items():
        (ppt / f"charts/chart{n}.xml").write_text(chart_xml(spec["cats"], spec["series"], spec["fmt"],
                                                            spec.get("horizontal", False), spec.get("log", False),
                                                            spec.get("legend", True), spec.get("vmax")))
        (ppt / f"charts/_rels/chart{n}.xml.rels").write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/package" '
            f'Target="../embeddings/Microsoft_Excel_Sheet{n}.xlsx"/></Relationships>')
        workbook(xlsx_copy, ppt / f"embeddings/Microsoft_Excel_Sheet{n}.xlsx", spec["cats"], spec["series"])
    xlsx_copy.unlink()
    shutil.copy(SHOTS / "390-dark-views.png", ppt / "media/views.png")
    shutil.copy(SHOTS / "1280-dark-01-login.png", ppt / "media/login.png")
    # a ninth slide: register it like the template's own
    ct = work / "[Content_Types].xml"
    c = ct.read_text()
    for part in ("/ppt/slides/slide9.xml", "/ppt/charts/chart2.xml"):
        kind = "presentationml.slide" if "slide" in part else "drawingml.chart"
        if part not in c:
            c = c.replace("</Types>", f'<Override PartName="{part}" ContentType="application/vnd.openxmlformats-'
                                      f'officedocument.{kind}+xml"/></Types>')
    ct.write_text(c)
    rels = ppt / "_rels/presentation.xml.rels"
    r = rels.read_text()
    if "slides/slide9.xml" not in r:
        r = r.replace("</Relationships>", '<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/'
                      'officeDocument/2006/relationships/slide" Target="slides/slide9.xml"/></Relationships>')
    rels.write_text(r)
    pres = ppt / "presentation.xml"
    p = pres.read_text()
    if 'r:id="rId99"' not in p:
        p = p.replace("</p:sldIdLst>", '<p:sldId id="264" r:id="rId99"/></p:sldIdLst>')
    pres.write_text(p)
    for sl in slides:
        (ppt / f"slides/slide{sl.n}.xml").write_text(sl.xml())
        (ppt / f"slides/_rels/slide{sl.n}.xml.rels").write_text(sl.rels_xml())
    core = work / "docProps/core.xml"
    core.write_text(re.sub(r"<dc:title>.*?</dc:title>", "<dc:title>Omnitrix</dc:title>", core.read_text()))
    OUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ct, "[Content_Types].xml")
        for f in sorted(work.rglob("*")):
            if f.is_file() and f != ct:
                z.write(f, f.relative_to(work).as_posix())
    shutil.rmtree(work)
    print(f"wrote {OUT}")


build()
