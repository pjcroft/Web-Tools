"""Slide transitions and entrance animations (python-pptx has no API for either).

Entrance effects play automatically in sequence ("after previous"), so presenters never click through
build steps unless they want to. A build step is a list of targets that appear together; a target is
(shape_id, paragraph_index_or_None).
"""
from lxml import etree as E

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
STAGGER = 300     # ms between build steps
DURATION = 450    # ms for one effect

TRANSITIONS = {
    'fade': '<p:fade/>',
    'push': '<p:push dir="l"/>',
    'wipe': '<p:wipe dir="l"/>',
}
# presetID, presetSubtype, filter
EFFECTS = {'fade': (10, 0, 'fade'), 'wipe': (22, 8, 'wipe(left)')}


def _frag(xml):
    return E.fromstring(f'<root xmlns:p="{P}">{xml}</root>')[0]


def _append_in_order(sld, element):
    """p:sld children must be ordered cSld, clrMapOvr, transition, timing, extLst."""
    order = ['cSld', 'clrMapOvr', 'transition', 'timing', 'extLst']
    rank = order.index(E.QName(element).localname)
    for i, child in enumerate(sld):
        if order.index(E.QName(child).localname) > rank:
            sld.insert(i, element)
            return
    sld.append(element)


def set_transition(slide, kind):
    if kind not in TRANSITIONS:
        return
    _append_in_order(slide._element, _frag(f'<p:transition spd="med">{TRANSITIONS[kind]}</p:transition>'))


def _target(spid, para):
    if para is None:
        return f'<p:spTgt spid="{spid}"/>'
    return f'<p:spTgt spid="{spid}"><p:txEl><p:pRg st="{para}" end="{para}"/></p:txEl></p:spTgt>'


def add_build(slide, steps):
    """steps: [{'targets': [(spid, para|None, kind)], 'effect': 'fade'|'wipe'}]; kind is 'sp', 'chart' or 'other'."""
    steps = [s for s in steps if s['targets']]
    if not steps:
        return
    ids = iter(range(3, 100000))
    inner = []
    build_text, build_shape, build_plain, build_chart = {}, set(), set(), set()
    for i, step in enumerate(steps):
        preset, subtype, flt = EFFECTS.get(step.get('effect', 'fade'), EFFECTS['fade'])
        effects = []
        for j, (spid, para, kind) in enumerate(step['targets']):
            node = 'afterEffect' if j == 0 else 'withEffect'
            tgt = _target(spid, para)
            effects.append(
                f'<p:par><p:cTn id="{next(ids)}" presetID="{preset}" presetClass="entr" presetSubtype="{subtype}" fill="hold" grpId="0" nodeType="{node}">'
                f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
                f'<p:tgtEl>{tgt}</p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
                f'<p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="{flt}"><p:cBhvr><p:cTn id="{next(ids)}" dur="{DURATION}"/>'
                f'<p:tgtEl>{tgt}</p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par>')
            if kind == 'chart':
                build_chart.add(spid)
            elif para is not None:
                build_text.setdefault(spid, True)
            elif kind == 'sp':
                build_shape.add(spid)
            elif kind == 'txt':
                build_plain.add(spid)
        inner.append(f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst><p:cond delay="{i * STAGGER}"/></p:stCondLst>'
                     f'<p:childTnLst>{"".join(effects)}</p:childTnLst></p:cTn></p:par>')
    bld = ''.join(f'<p:bldP spid="{s}" grpId="0" build="p"/>' for s in build_text)
    bld += ''.join(f'<p:bldP spid="{s}" grpId="0" animBg="1"/>' for s in sorted(build_shape - set(build_text)))
    bld += ''.join(f'<p:bldP spid="{s}" grpId="0"/>' for s in sorted(build_plain - set(build_text)))
    bld += ''.join(f'<p:bldGraphic spid="{s}" grpId="0"><p:bldAsOne/></p:bldGraphic>' for s in sorted(build_chart))
    xml = ('<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
           '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
           '<p:par><p:cTn id="%d" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
           '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>%s</p:childTnLst></p:cTn></p:par>'
           '</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
           '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
           '</p:childTnLst></p:cTn></p:par></p:tnLst>%s</p:timing>') % (next(ids), ''.join(inner), f'<p:bldLst>{bld}</p:bldLst>' if bld else '')
    _append_in_order(slide._element, _frag(xml))
