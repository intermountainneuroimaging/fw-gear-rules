from pathlib import Path
import sys, subprocess, os, logging
import flywheel
import glob
import pandas as pd
from time import sleep
import re
import tempfile
import json
from dateutil.tz import tzutc
from datetime import datetime, timedelta


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('main')


## Helper Function for getting date
def get_x_days_ago(x, date=None):
    if date is None:
        date = datetime.now()
    return date - timedelta(days=x)


def run_gear(gear, config, inputs, tags, dest, analysis_label=[]):
    """Submits a job with specified gear and inputs.
    
    Args:
        gear (flywheel.Gear): A Flywheel Gear.
        config (dict): Configuration dictionary for the gear.
        inputs (dict): Input dictionary for the gear.
        tags (list): List of tags for gear
        dest (flywheel.container): A Flywheel Container where the output will be stored.
        analysis_label (str): label for gear.
        
    Returns:
        str: The id of the submitted job (for utility gear) or analysis container (for analysis gear).
        
    """
    try:
        # Run the gear on the inputs provided, stored output in dest constainer and returns job ID
        if not analysis_label:
            label = gear['gear']['name']+datetime.now().strftime(" %x %X")
        else:
            label = analysis_label
        gear_job_id = gear.run(analysis_label=label, config=config, inputs=inputs, tags=tags, destination=dest)
        log.debug('Submitted job %s', gear_job_id)
        
        return gear_job_id
    except flywheel.rest.ApiException:
        log.exception('An exception was raised when attempting to submit a job for %s',
                      gear_job_id.name)
        

def session_analysis_exists(container, gear_info, status=["complete","running","pending"], status_bool_type="any", count_up_to_failures=1):
    # Returns True if analysis already exists with a running or complete status, else false
    # make sure to pass full session object (use fw.get_session(session.id))
    #
    #Get all analyses for the session
    flag=False
    counter=0
    
    #handle checks for any version of gear or specific version 
    if "/" in gear_info:
        gear_name = gear_info.split("/")[0]
        gear_version = gear_info.split("/")[1]  # allow wildcard expressions here to check for multiple gear versions 
    else:
        gear_name = gear_info
        gear_version = []
    
    # check all session analyses
    for analysis in container.analyses:
        #only print ones that match the analysis label
        if gear_name == analysis.gear_info.name:
            if gear_version:
                r1 = re.compile(gear_version)
                if not r1.search(analysis.gear_info["version"]):
                    continue
                    
            #filter for only successful job
            analysis_job=analysis.job
            if not hasattr(analysis_job,'state'): 
                flag=True
            else:
                if any(analysis_job.state in string for string in status):
                    if analysis_job.state == "failed":
                        counter += 1
                        if counter >= count_up_to_failures:
                            flag=True
                    else:
                        flag=True
                else:
                    # if any of the analyses that match name and version, but do not match status
                    if status_bool_type == "all":
                        return False
    
    return flag


def acquisition_analysis_exists(container, gear_info, status=["complete","running","pending"], status_bool_type="any", count_up_to_failures=1):
    # Returns True if analysis already exists with a running or complete status, else false
    # make sure to pass full session object (use fw.get_session(session.id))
    #
    #Get all analyses for the session
    flag=False
    counter=0
    
    #handle checks for any version of gear or specific version 
    if "/" in gear_info:
        gear_name = gear_info.split("/")[0]
        gear_version = gear_info.split("/")[1]  # allow wildcard expressions here to check for multiple gear versions 
    else:
        gear_name = gear_info
        gear_version = []
                    
    # check all acqusition analysis (this is needed for pre-curate gear)
    acq_analyses = [ fw.get_acquisition(a.id).analyses for a in container.acquisitions.find()] # pull analyses from all acquisitions
    acq_analyses = [item for sublist in acq_analyses for item in sublist] #flatten list of acquisitons
    for analysis in acq_analyses:
        #only print ones that match the analysis label
        if gear_name == analysis.gear_info.name:
            if gear_version:
                r1 = re.compile(gear_version)
                if not r1.search(analysis.gear_info["version"]):
                    continue
                    
            #filter for only successful job
            analysis_job=analysis.job
            if not hasattr(analysis_job,'state'): 
                flag=True
            else:
                if any(analysis_job.state in string for string in status):
                    if analysis_job.state == "failed":
                        counter += 1
                        if counter >= count_up_to_failures:
                            flag=True
                    else:
                        flag=True
                else:
                    # if any of the analyses that match name and version, but do not match status
                    if status_bool_type == "all":
                        return False
    
    
    return flag


def run_auto_gear(session_id):
    full_session=fw.get_session(session_id)
    project = fw.get_project(full_session["parents"]["project"])

    template_file = project.get_file("gears_template.json")

    if not template_file:
        return  # if template file doesnt exist for project, skip...

    with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpdir:

        template_file.download(os.path.join(tmpdir,template_file['name']))

        with open(os.path.join(tmpdir,template_file['name'])) as f:
            template = json.load(f)


    for itr, itr_template in enumerate(template["analysis"]):
    
        # pull session and project info at the beggining of each gear call in case changes have occured
        full_session=fw.get_session(session_id)

        # get gear for analysis
        if "gear-version" in itr_template:
            my_gear_name=itr_template["gear-name"]+"/"+itr_template["gear-version"]
        else: 
            my_gear_name=itr_template["gear-name"]

        gear = fw.lookup("gears"+"/"+my_gear_name)

        # intialize values
        run_flag=True
        mylabel = gear['gear']['name']+datetime.now().strftime(" %x %X")
        myinputs = dict()
        numfails = 1



        # pull number of failures allowed
        if "count-failures" in itr_template:
            numfails=itr_template["count-failures"]


        # ------------------------------- #
        # ----------- checks ------------ #
        # ------------------------------- #

        # 1. check if prerequisites are satisfied
        if "prerequisites" in itr_template:
            for prereq in itr_template["prerequisites"]:
                if not (session_analysis_exists(full_session, prereq, status=["complete"]) or 
                        acquisition_analysis_exists(full_session, prereq, status=["complete"], status_bool_type=itr_template["prerequisites"][prereq])):
                    log.info("PREREQUISITES not met: Skipping... %s for Project %s Subject %s Session %s %s", gear.gear.name, project.label, full_session.subject.label, full_session.label,full_session.id)
                    run_flag = False

        if run_flag == False: continue

        # 2. check if analysis already run 
        if session_analysis_exists(full_session, my_gear_name, status=["complete","running","pending", "failed"], count_up_to_failures=numfails):
            log.info("EXISTING analysis found: Skipping... %s for Project %s Subject %s Session %s %s", gear.gear.name, project.label, full_session.subject.label, full_session.label,full_session.id)
            run_flag = False 
            continue

        # 3. check for any completeness or session tags
        if "completeness-tags" in itr_template:
            if "COMPLETENESS" not in full_session.info:
                run_flag = False
                log.info("Completeness conditions not accessible ... Project %s Subject %s Session %s %s ", project.label, full_session.subject.label, full_session.label, full_session.id)
            else:
                for tag in itr_template["completeness-tags"]:
                    if not full_session.info["COMPLETENESS"][tag]:
                        run_flag = False
                        log.info("Completeness condition not satified: %s ... Project %s Subject %s Session %s %s ",tag, project.label, full_session.subject.label, full_session.label, full_session.id)

        if run_flag == False: continue

        if "session-tags" in itr_template:
            for tag in itr_template["session-tags"]:
                if tag not in full_session.tags:
                    run_flag = False
                    log.info("Missing Required session tag: %s ... Project %s Subject %s Session %s %s ",tag, project.label, full_session.subject.label, full_session.label, full_session.id)

        if run_flag == False: continue

        # ------------------------------- #
        # ------------ run -------------- #
        # ------------------------------- #

        # if analysis should run - generate all inputs then run...
        for key in itr_template["inputs"]:

            # put input files in the format flywheel gear.run expects...

            fw_container = fw.get_container(full_session.parents[itr_template["inputs"][key]["parent-container"]])

            # if 'value' key is passed for an input, just get the file from flywheel using given name"
            if "value" in itr_template["inputs"][key]:
                file_found = fw_container.get_file(itr_template["inputs"][key]["value"])
                if "optional" in itr_template["inputs"][key] and itr_template["inputs"][key]["optional"] == True and not file_found:
                        pass
                else:
                    myinputs[key]=fw_container.get_file(itr_template["inputs"][key]["value"])

            # if 'regex' key is passed from an input, look for files matching the regular expression, save file if a match is found
            elif "regex" in itr_template["inputs"][key]:

                namelist = [file['name'] for file in fw_container.files]

                r1=re.compile(itr_template["inputs"][key]["regex"])
                matching_names = [x for x in namelist if r1.search(x)]

                if len(matching_names) == 1:
                    myinputs[key]=fw_container.get_file(matching_names[0])
                    log.debug("files found for analysis: %s"," ,".join(matching_names))

                elif len(matching_names) > 1:
                    log.debug("files found for analysis: %s"," ,".join(matching_names))
                    log.error("not sure which file to use, multiple matches...skipping")
                    run_flag = False 

                elif len(matching_names) < 1:
                    # check if input was optionl, if so, ok that is wasn't found, proceed
                    if "optional" in itr_template["inputs"][key] and itr_template["inputs"][key]["optional"] == True:
                        pass
                    else:
                        log.error("unable to locate required file input...skipping")
                        run_flag = False 

        # pull config
        myconfig = itr_template["config"]

        # pull tags
        mytags = itr_template["tags"]

        # pull custom analysis label (if present)
        if "custom-label" in itr_template:
            mylabel = itr_template["custom-label"]+datetime.now().strftime(" %x %X")

        run_gear(gear, myconfig, myinputs, mytags, full_session, analysis_label=mylabel)
        log.info('RUNNING gear: %s Project %s Subject %s, Session %s %s ', mylabel, project.label, full_session.subject.label, full_session.label, full_session.id)
        sleep(itr_template["sleep_seconds"])

    
    
    
if __name__ == "__main__":
    #Setup the flywheel client
    fw = flywheel.Client('')
    fw.get_config().site.api_url

    created_by = get_x_days_ago(7).strftime('%Y-%m-%d')
    filtered_sessions=fw.sessions.find(f'created>{created_by}')

    #Loop through sessions and see which ones apply for the gear rule to kick off
    for session in filtered_sessions:
        sid = session.id
        print(session.subject.label+" "+session.label)

        run_auto_gear(sid)