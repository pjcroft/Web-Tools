"""Presentation styles (the old "Purpose" list).

Each style tells the AI which slide types to favour and how to write, sets a sensible slide
count, and has an example deck (`example`) that make_examples.py renders through the real
exporter into static/examples/<id>.jpg, so the preview shown in the UI is genuine output.
"""

STYLES = [
    {
        'id': 'project_update', 'label': 'Project update', 'count': 8,
        'blurb': 'Status, progress figures, milestones and next steps.',
        'guidance': 'Audience: project team and sponsors. Favour stats for headline progress numbers, a timeline for milestones, '
                    'and a chart only for real tracked figures. Finish with risks/next steps. Tone: factual, brief, plain.',
        'mix': 'stats, timeline, chart, content',
        'example': [
            {'layout': 'cover', 'title': 'Line 4 installation update', 'subtitle': 'Week 12 status report'},
            {'layout': 'stats', 'title': 'Where we are', 'stats': [
                {'value': '78%', 'label': 'Mechanical complete', 'note': 'Up from 62% last month'},
                {'value': '14', 'label': 'Open punch items', 'note': '6 closed this week'},
                {'value': '3 wks', 'label': 'To site acceptance', 'note': 'On plan'}],
             'takeaway': 'On track for site acceptance in week 15.'},
            {'layout': 'timeline', 'title': 'Milestones', 'steps': [
                {'title': 'Delivery', 'text': 'All crates on site'}, {'title': 'Mechanical', 'text': 'Frames and conveyors aligned'},
                {'title': 'Electrical', 'text': 'Cabinets wired and tested'}, {'title': 'Acceptance', 'text': 'Customer witness test'}]},
        ],
    },
    {
        'id': 'executive', 'label': 'Executive summary', 'count': 5,
        'blurb': 'Short and decisive: the numbers, the ask, the decision.',
        'guidance': 'Audience: senior decision makers with little time. Maximum 6 slides. Lead with the conclusion. Use stats for key figures, '
                    'one chart if numbers allow, and end with a clear decision or ask. Every slide needs a takeaway sentence. Tone: confident, concise.',
        'mix': 'stats, chart, two_column, quote',
        'example': [
            {'layout': 'cover', 'title': 'Service performance review', 'subtitle': 'Executive summary'},
            {'layout': 'chart', 'title': 'Uptime is up in every region',
             'chart': {'type': 'column', 'categories': ['EMEA', 'Americas', 'APAC'], 'series': [
                 {'name': 'Q2', 'values': [94, 91, 89]}, {'name': 'Q3', 'values': [97, 95, 93]}], 'unit': '%'},
             'bullets': ['Largest gain in APAC', 'EMEA above target'], 'takeaway': 'All regions now within 3 points of the 98% goal.'},
            {'layout': 'two_column', 'title': 'Decision required', 'columns': [
                {'title': 'Option A: extend', 'bullets': ['Keep current contract', 'Lower upfront cost']},
                {'title': 'Option B: upgrade', 'bullets': ['New monitoring tier', 'Faster response times']}]},
        ],
    },
    {
        'id': 'customer', 'label': 'Customer presentation', 'count': 10,
        'blurb': 'Polished and benefit-led, with visuals and a clear story.',
        'guidance': 'Audience: a customer or prospect. Focus on benefits and outcomes over internal detail. Use images where provided, '
                    'a quote or a stats slide for proof, and a timeline for what happens next. Tone: warm, professional, confident.',
        'mix': 'image_text, stats, quote, timeline',
        'example': [
            {'layout': 'cover', 'title': 'Evolve your production floor', 'subtitle': 'Prepared for Northfield Manufacturing'},
            {'layout': 'stats', 'title': 'What customers see', 'stats': [
                {'value': '30%', 'label': 'Faster throughput'}, {'value': '45%', 'label': 'Less material waste'},
                {'value': '12 mo', 'label': 'Typical payback'}]},
            {'layout': 'quote', 'quote': 'The installation was on time and the line has not stopped since.', 'author': 'Plant Manager, existing customer'},
        ],
    },
    {
        'id': 'proposal', 'label': 'Proposal', 'count': 10,
        'blurb': 'Problem, solution, scope, price and timeline.',
        'guidance': 'Audience: a buyer evaluating an offer. Structure: need, proposed solution, scope/deliverables, a table for pricing or '
                    'options when figures exist, timeline, and next steps. Never invent prices. Tone: persuasive but precise.',
        'mix': 'two_column, table, timeline, content',
        'example': [
            {'layout': 'cover', 'title': 'Automation upgrade proposal', 'subtitle': 'Scope, schedule and investment'},
            {'layout': 'table', 'title': 'Options at a glance', 'table': {'header': ['Option', 'Scope', 'Lead time', 'Investment'], 'rows': [
                ['Essential', 'Core line', '12 weeks', 'EUR 480k'], ['Standard', 'Line + software', '14 weeks', 'EUR 620k'],
                ['Premium', 'Full integration', '18 weeks', 'EUR 810k']]}, 'takeaway': 'Standard covers the stated requirements.'},
            {'layout': 'two_column', 'title': 'Included and excluded', 'columns': [
                {'title': 'Included', 'bullets': ['Equipment and installation', 'Operator training']},
                {'title': 'Excluded', 'bullets': ['Building works', 'Local permits']}]},
        ],
    },
    {
        'id': 'training', 'label': 'Training', 'count': 12,
        'blurb': 'Step-by-step learning with agenda, process and recap.',
        'guidance': 'Audience: learners. Start with an agenda and learning goals. Teach in small steps: timeline layout for procedures, '
                    'two_column for do/don\'t, content for explanations. Use section slides between modules and end with a recap. Tone: clear, instructional.',
        'mix': 'agenda, timeline, two_column, section',
        'example': [
            {'layout': 'cover', 'title': 'Safe machine start-up', 'subtitle': 'Operator training, module 1'},
            {'layout': 'agenda', 'title': 'Agenda', 'bullets': ['Safety checks', 'Start-up sequence', 'Common faults', 'Recap and questions']},
            {'layout': 'timeline', 'title': 'Start-up sequence', 'steps': [
                {'title': 'Inspect', 'text': 'Guards and e-stops in place'}, {'title': 'Power', 'text': 'Main isolator on'},
                {'title': 'Home', 'text': 'Run the homing cycle'}, {'title': 'Run', 'text': 'Load the first job'}]},
        ],
    },
    {
        'id': 'review', 'label': 'Technical / post-install review', 'count': 8,
        'blurb': 'Findings, data, issues and corrective actions.',
        'guidance': 'Audience: engineers and service managers. Show what happened, evidence and actions. Use a table for issue lists, a chart '
                    'for trends only when numbers are given, two_column for cause versus action, and image slides for drawings/photos. Tone: precise, neutral.',
        'mix': 'table, chart, two_column, image',
        'example': [
            {'layout': 'cover', 'title': 'Post-installation review', 'subtitle': 'Findings and corrective actions'},
            {'layout': 'table', 'title': 'Issue log', 'table': {'header': ['Issue', 'Cause', 'Owner', 'Status'], 'rows': [
                ['Sensor drift', 'Loose bracket', 'Service', 'Closed'], ['Slow feed', 'Parameter set', 'Software', 'Open'],
                ['Noise at axis 3', 'Bearing', 'Service', 'Open']]}},
            {'layout': 'chart', 'title': 'Downtime by week', 'chart': {'type': 'line', 'categories': ['W1', 'W2', 'W3', 'W4', 'W5'],
                'series': [{'name': 'Hours', 'values': [14, 11, 9, 5, 3]}], 'unit': 'h'}, 'bullets': ['Steady decline since W1']},
        ],
    },
    {
        'id': 'general', 'label': 'General presentation', 'count': 8,
        'blurb': 'A balanced mix when you are not sure which style fits.',
        'guidance': 'Audience: general. Use a balanced variety of slide types and let the content decide. Tone: clear, professional.',
        'mix': 'content, two_column, stats, timeline',
        'example': [
            {'layout': 'cover', 'title': 'Introducing our new service', 'subtitle': 'Overview'},
            {'layout': 'content', 'title': 'Why it matters', 'bullets': ['Faster response — remote diagnostics cut visit times',
                'Lower cost — fewer unplanned stops', 'Better planning — shared visibility of service history']},
            {'layout': 'two_column', 'title': 'Before and after', 'columns': [
                {'title': 'Today', 'bullets': ['Manual reports', 'Slow handover']}, {'title': 'With the new service', 'bullets': ['Live dashboards', 'Instant handover']}]},
        ],
    },
]

STYLE_BY_ID = {s['id']: s for s in STYLES}
DEFAULT_STYLE = 'project_update'
# Old saved forms and API clients sent the label text; map it to the new id.
LEGACY = {'Project update': 'project_update', 'Customer presentation': 'customer', 'Training': 'training',
          'Proposal': 'proposal', 'General presentation': 'general'}


def resolve_style(value):
    value = LEGACY.get(value, value)
    return STYLE_BY_ID.get(value) or STYLE_BY_ID[DEFAULT_STYLE]


def public_styles():
    return [{'id': s['id'], 'label': s['label'], 'blurb': s['blurb'], 'count': s['count'], 'mix': s['mix'],
             'image': f"examples/{s['id']}.jpg"} for s in STYLES]
