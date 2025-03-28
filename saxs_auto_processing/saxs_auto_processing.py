from pyCHX.chx_packages import *
import papermill as pm
import os
import sys
sys.path.insert(0, "/nsls2/data/chx/shared/CHX_Software/packages/standard_functions/")
from standard_functions import *

def chx_saxs_export(scan, glob_settings_dict,_base_path_, _base_path_pass_, verbose=False):
    """
    Running SAXS export template via papermill
    scan: 162000 or [162000,0,50] or [ [162000,{...}] or [162000,0,50,{...}]
    glob_settings_dict: dictionary with (mandatory): user, cycle, template name and (optional): processing instructions
    _base_path_, _base_path_pass_ just passed from chx_analysis_setup
    """
    # consolidate global settings dict with potential over-writes for this specific scan
    if type(scan) != int and len(scan)>1:
        if type(scan[-1]) == dict:
            for k in scan[-1].keys():
                glob_settings_dict[k] = scan[-1][k]
            scan=scan[:-1] # stripped the dict-part
    glob_settings_dict['scan_no'] = scan
    # need access to full metadata for this scan:
    if type(scan) == int:
        scan_list=[scan]
    elif type(scan) == list:
        scan_list = [scan[0]]
    (scan_list,uid_list)=get_uid_list(scan_list,user=glob_settings_dict['user'],cycle=glob_settings_dict['cycle'],verbose=False)
    md=get_meta_data(uid_list[0])
    if 'proposal' in md.keys():
        baseDir = _base_path_pass_
        user_dir = baseDir + '%s/pass_%s/'%(md['cycle'],md['proposal']['proposal_id'])
    else:
        baseDir = _base_path_
        user_dir = baseDir + '%s/%s/'%(glob_settings_dict['cycle'],glob_settings_dict['user'])
    # full path to template notebook:
    template_pipeline = user_dir+glob_settings_dict['template_name']
    # full path to save papermill copy of template:
    output_pipeline = user_dir+'Results/Exports/notebooks/%s_%s.ipynb'%(glob_settings_dict['template_name'].split('.')[0],md['scan_id'])
    # make sure that the required folders exist:
    os.makedirs(user_dir+'Results/Exports/', exist_ok=True)
    os.makedirs(user_dir+'Results/Exports/notebooks/', exist_ok=True)

    # execute notebook through papermill
    pm.execute_notebook(
    template_pipeline, output_pipeline,         
       parameters = glob_settings_dict,
        kernel_name='python3', report_mode=True )