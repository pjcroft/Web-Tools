"""Export the app's supported schedule as Microsoft Project MSPDI XML."""
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring

NS='http://schemas.microsoft.com/project'

def export_xml(project):
    root=Element('Project',xmlns=NS)
    def add(parent,key,value):
        node=SubElement(parent,key); node.text=str(value); return node
    for key,value in [('SaveVersion',14),('Name',project['name']),('ScheduleFromStart',1),('StartDate',project['start']+'T08:00:00'),('CalendarUID',1),('DefaultStartTime','08:00:00'),('DefaultFinishTime','17:00:00'),('MinutesPerDay',480),('MinutesPerWeek',2400),('DaysPerMonth',20)]: add(root,key,value)
    calendars=SubElement(root,'Calendars'); cal=SubElement(calendars,'Calendar')
    for key,value in [('UID',1),('Name','Standard'),('IsBaseCalendar',1),('BaseCalendarUID',-1)]: add(cal,key,value)
    days=SubElement(cal,'WeekDays')
    for number in range(1,8):
        day=SubElement(days,'WeekDay'); add(day,'DayType',number); add(day,'DayWorking',int(number not in (1,7)))
        if number not in (1,7):
            times=SubElement(day,'WorkingTimes')
            for start,end in [('08:00:00','12:00:00'),('13:00:00','17:00:00')]:
                time=SubElement(times,'WorkingTime'); add(time,'FromTime',start); add(time,'ToTime',end)
    tasks=SubElement(root,'Tasks'); counters=[]
    for index,t in enumerate(project['tasks'],1):
        level=t['level']; counters=counters[:level+1]
        while len(counters)<=level: counters.append(0)
        counters[level]+=1
        task=SubElement(tasks,'Task')
        # Fixed date tasks use manual scheduling, matching the PC Plan import model.
        for key,value in [('UID',t['id']),('ID',index),('Name',t['name']),('Type',1),('IsNull',0),('WBS','.'.join(map(str,counters))),('OutlineNumber','.'.join(map(str,counters))),('OutlineLevel',level+1),('Start',t['start']+'T08:00:00'),('Finish',t['finish']+('T08:00:00' if t['kind']=='milestone' else 'T17:00:00')),('Duration',f"PT{0 if t['kind']=='milestone' else round(t['duration']*480)}M0S"),('DurationFormat',7),('Milestone',int(t['kind']=='milestone')),('Summary',int(t['kind']=='phase')),('CalendarUID',1),('Manual',int(t.get('mode')=='manual'))]: add(task,key,value)
        if t.get('mode')=='manual':
            add(task,'ManualStart',t['start']+'T08:00:00'); add(task,'ManualFinish',t['finish']+('T08:00:00' if t['kind']=='milestone' else 'T17:00:00'))
        else:
            add(task,'ConstraintType',4); add(task,'ConstraintDate',t['start']+'T08:00:00')
        for predecessor in t['deps']:
            link=SubElement(task,'PredecessorLink')
            add(link,'PredecessorUID',predecessor); add(link,'Type',1); add(link,'CrossProject',0); add(link,'LinkLag',0); add(link,'LagFormat',7)
    owners=list(dict.fromkeys(t['owner'] for t in project['tasks'] if t['owner']))
    resources=SubElement(root,'Resources')
    for uid,name in enumerate(owners,1):
        resource=SubElement(resources,'Resource'); add(resource,'UID',uid); add(resource,'ID',uid); add(resource,'Name',name); add(resource,'Type',1)
    assignments=SubElement(root,'Assignments')
    for index,t in enumerate(project['tasks'],1):
        if t['owner'] and t['kind']=='task':
            assignment=SubElement(assignments,'Assignment')
            for key,value in [('UID',index),('TaskUID',t['id']),('ResourceUID',owners.index(t['owner'])+1),('Units',1)]: add(assignment,key,value)
    return tostring(root,encoding='utf-8',xml_declaration=True)
