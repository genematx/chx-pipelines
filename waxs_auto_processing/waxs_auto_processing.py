from pyCHX.chx_packages import *
from pyCHX.chx_generic_functions import append_txtfile
from pyCHX.chx_xpcs_xsvs_jupyter_V1 import get_uids_in_time_period
import json
import dask
import os
import papermill as pm
import time
import numpy as np
from termcolor import colored
import pandas as pd
from pandas.io.formats.style import Styler
import sys
sys.path.insert(0, "/nsls2/data/chx/shared/CHX_Software/packages/standard_functions/")
from standard_functions import get_uid_list, pseudo_Voigt
from itertools import groupby
import glob
import uuid
from tqdm import tqdm
from decimal import Decimal
from scipy.optimize import fsolve, differential_evolution,dual_annealing,shgo,direct, Bounds

##################### papermill call to run WAXS template ###############################################################
def chx_waxs_analysis(uid, pass_dir, calibration_uid, insert_dict=None, verbose=False):
    """
    Running WAXS analysis template via papermill
    uid: uid for wich WAXS analysis shall be run
    path_dir: path up to .../cycle/user/... or .../cycle/pass-123456/
    calibration_uid: uid of the calibration data (calibration file needs to be created first!); IF calibration_uid is a scan number, taking user and cycle from md to convert to uid
    insert_dict: dictionary to insert custom parameters via papermill; NOTE: mandatory key is 'template_name'!!!
    """
    md=get_meta_data(uid)
    param_dict={'analyst':md['user'],'user':md['user'],'cycle':md['cycle'],'scan_list':[uid],'calibration':calibration_uid}
    for k in insert_dict.keys():
        if k not in ['template_name']:
            param_dict[k]=insert_dict[k]

    resultsDir = pass_dir+'/Results/'
    outDir = pass_dir+'/ResPipelines/'
    ### need to make sure these exist!!
    os.makedirs(resultsDir, exist_ok=True)
    os.makedirs(outDir, exist_ok=True)
    template_name = insert_dict['template_name'].split('.')[0] #split: just in case template name alreay had file ending
    template_pipeline = pass_dir+'/AutoRuns/'+template_name+'.ipynb'
    output_pipeline=outDir+template_name+'_%s.ipynb'%uid

    # execute notebook through papermill
    pm.execute_notebook(
    template_pipeline, output_pipeline,         
       parameters = param_dict,
        kernel_name='python3', report_mode=True )

#################### loop that gets new uids for processing from json-file and calls papermill loop #########################
def run_waxs_papermill_loop(waxs_uids_dict_file,calibration_uid,insert_dict,txt_filename,pass_dir,empty_list_timeout=None,verbose=False):
    """
    wrapper for chx_waxs_analysis.py (which runs the actual papermill)
    - gets uids to be processed from waxs_uids_dict_file
    - manages errors and exceptions encountered during running the template notebook via papermill
    - empty_list_timeout: timeout in [min]: loop will stop if list of uids to be processed is emtpy for longer than this timeout
    - txt_filename: .txt file to save some basic information about the processing for each uid
    """
    time_ref=time.time()
    run_condition = True; write_header = True
    txt_dir='/';
    for l in waxs_uids_dict_file.split('/')[1:-1]:
        txt_dir+=l+'/'
    
    while run_condition:
        display(clear=True,wait =True)
        try:
            f = open(waxs_uids_dict_file)
            tmp = json.load(f);f.close()
            uid_dict=json.loads(tmp);del tmp
            file_retrieved=True
        except:
            print('something went wrong with reading %s....-> does this file exist?\n%s:  waiting for WAXS data to process....'%(waxs_uids_dict_file,time.ctime(time.time())))
            file_retrieved=False
            time.sleep(10)

        if file_retrieved:
            todo=[]
            for u in uid_dict['waxs_uids']:
                if u not in uid_dict['processed'].keys():
                    todo.append(u)
            if len(todo)>0: # if not, there are currently no uids to be processed
                time_ref=time.time()
                todo = np.flipud(todo)
                print('NEXT UIDs to be PROCESSED: ')
                for i in range(3):
                    if len(todo)>i:
                        print('[%s]   scan_id: %s    uid: %s'%(i,db[todo[i]].start['scan_id'],todo[i]))
                if len(todo)>3: print('... (total: %s uids)'%len(todo))

                # select uid to process
                cur_uid=todo[0]
                print('processing uid: %s'%cur_uid)
                uid_dict['in_processing'].append(cur_uid)

                uid_dict['processed'][cur_uid]={'start':time.time(),'stop':'N.A.','status':'started'}
                with open(waxs_uids_dict_file, "w") as outfile:
                            json.dump(json.dumps(uid_dict), outfile)
                print('updated %s '%waxs_uids_dict_file)            
                
                try:
                    t0 = time.time()
                    insert_dict['insert_timestamp']=t0
                    chx_waxs_analysis(cur_uid, pass_dir, calibration_uid, insert_dict, verbose=False) ## actual data processing happens here
                    success = 'completed'
                except:
                    success='failed'
                    ################ just for testing!!! ##################
                    # from random import random
                    # if random() >.5:
                    #    success= 'completed' 
                    #######################################################
                ts = np.round((time.time()-t0)/60,1)
                ### update json file
                try:
                    f = open(waxs_uids_dict_file)
                    tmp = json.load(f);f.close()
                    uid_dict=json.loads(tmp);del tmp
                except:
                    print('something went wrong with reading %s....-> does this file exist?'%waxs_uids_dict_file)

                in_process = uid_dict['in_processing']
                if len(in_process)>0:
                    try:
                        uid_dict['in_processing'].remove(cur_uid)
                    except:
                        print('somehow the uid: %s already disappeared from the processing list...'%cur_uid)
                uid_dict['processed'][cur_uid]['stop']=time.time();uid_dict['processed'][cur_uid]['status']= success
                with open(waxs_uids_dict_file, "w") as outfile:
                            json.dump(json.dumps(uid_dict), outfile)
                print('updated %s '%waxs_uids_dict_file)
                
                # write txt file:
                if write_header:
                        txt_header = 'uid, comp_time, comp_status';write_header=False
                else: txt_header = ''
                #txt_content =   [ cur_uid, ts, success ]
                txt_content = ['%s   %s   %s'%(cur_uid, ts, success)]
                append_txtfile( txt_dir + txt_filename, data=txt_content, fmt='%s',
                            delimiter=',', header= txt_header) 
                
            else: #todo list is empty
                print('%s:   waiting for uids to be processed...'%time.ctime(time.time()))
                if empty_list_timeout !=None and (time.time()-time_ref)/60>empty_list_timeout:
                    run_condition=False
                    print('TIMEOUT: stopping to look for new uids.')
                time.sleep(10)

######### loop that gets new uids for processing from database, adds them to json-file and visualizes the processing queue and statistics on processed data ##
def WAXS_queue(waxs_uids_dict_file,start_uid,empty_list_timeout=None,stop_uid=None,statistic_cutoff=720,verbose=False):
    """
    collect WAXS uids in json file for processing by 'run_waxs_papermill_loop(...)'
    waxs_uids_dict_file: path and name to json file (existing or to be created) to keep the uid dictionary
    start_uid: uid to start searching from (this should NOT be a scan_id)
    empty_list_timeout: None -> never stops looking for new WAXS uids; otherwise: will stop after not finding new uids for x [min]
    statistic_cutoff: showing statistics for the last 20 processed datasets or the subset that finished within the last statistic_cutoff [min]; if None: show last 20 completed processing, no matter how old
    """

    run_condition = True
    time_ref=time.time()

    while run_condition:
        try:
            f = open(waxs_uids_dict_file)
            tmp = json.load(f);f.close()
            uid_dict=json.loads(tmp);del tmp
        except:
            print('something went wrong with reading %s....-> does this file exist?'%waxs_uids_dict_file)
            print('want to start with a new dictionary file? yes/no');response=input()
            if response in ['yes','Yes','YES','y','Y']:
                uid_dict={'start_time':db[start_uid].start['time'],'all_uids':[],'waxs_uids':[],'waiting_list':[],'in_processing':[],'processed':{}} # added waiting list for uids that have started collection, but didn't finish yet...
                print('Creating new dictionary file!')
            else:
                raise Exception('ERROR: check dictionary filename and path or create a new dictionary.')

        display(clear=True,wait =True)
        plt.close()
        if 'last_time_checked' in uid_dict.keys() and uid_dict['last_time_checked']>uid_dict['start_time']:
            start_time=uid_dict['last_time_checked']
        else:
            start_time = uid_dict['start_time']
        current_time = time.time() # for production
        uid_dict['last_time_checked']=current_time
        d=get_uids_in_time_period(start_time,current_time)
        for u in d[1]:
            if u not in uid_dict['all_uids']: # -> this is a new uid
                uid_dict['all_uids'].append(u)
                try:
                    if 'pilatus800' in db[u].start['detectors']: # -> this a WAXS uid                        
                        try:  # 1) this has been finished collecting data and is ready for processing OR it is finished, but exit status is not success
                            if db[u].stop['exit_status'] == 'success':
                                uid_dict['waxs_uids'].append(u)
                            if db[u].stop['exit_status'] != 'success':
                                uid_dict['processed'][u]={'start':'N.A.','stop':time.time(),'status':'failed'}
                        except: #2) this uid doesn't have an exit status yet as it is still being collected
                            uid_dict['waiting_list'].append(u)
                    # if 'pilatus800' in db[u].start['detectors']: # -> this a WAXS uid
                    #     uid_dict['waxs_uids'].append(u)
                    #     if db[u].stop['exit_status'] != 'success': # -> this run has been aborted and cannot be processed anyways 
                    #         uid_dict['processed'][u]={'start':'N.A.','stop':time.time(),'status':'failed'} # -> move aborted run to 'processed' with status 'failed'; start: N.A. could be used to differentiate this case from uids that were processed, but failed
                except:
                    pass
        # check the waiting list:
        wl = len(uid_dict['waiting_list'])
        if wl>0:
            print('checking %s uid(s) on the waiting list...')
        for u in uid_dict['waiting_list']:
            try: # do we have an exit status by now?
                if db[u].stop['exit_status'] == 'success':
                    uid_dict['waxs_uids'].append(u)
                    uid_dict['waiting_list'].remove(u)
                if db[u].stop['exit_status'] != 'success':
                    uid_dict['processed'][u]={'start':'N.A.','stop':time.time(),'status':'failed'}
                    uid_dict['waiting_list'].remove(u)
            except:
                pass # we'll keep looking for updates...
                    
        display(clear=True,wait =True)
        with open(waxs_uids_dict_file, "w") as outfile:
                json.dump(json.dumps(uid_dict), outfile)
        print('updated %s '%waxs_uids_dict_file)
        
        ### visualize queue:
        todo=[]
        for u in uid_dict['waxs_uids']:
            if  u not in list(uid_dict['processed'].keys()):
                todo.append(u)
        todo=np.flipud(todo) #get_uids_in_time_period seems to return uids in order newest -> oldest, but we want to process from old -> new....
        print('NEXT UIDs to be PROCESSED: ')
        for i in range(3):
            if len(todo)>i:
                print('[%s]   scan_id: %s    uid: %s'%(i,db[todo[i]].start['scan_id'],todo[i]))
        if len(todo)>3: print('... (total: %s uids)'%len(todo))
        if len(uid_dict['in_processing']) > 0:
            time_ref=time.time()
            print('UIDs CURRENTLY being PROCESSED:')
            for ii,i in enumerate(uid_dict['in_processing']):
                si = db[i].start['scan_id']
                rt = time.time()-uid_dict['processed'][i]['start']
                if rt < 300:
                    rt_unit = 's'
                else:
                    rt=rt/60;rt_unit = 'min'
                print('[%s]   scan_id: %s  uid: %s   running since: %0f %s'%(ii,si,i,rt,rt_unit))
        else:
            if empty_list_timeout !=None and (time.time()-time_ref)/60>empty_list_timeout:
                run_condition=False
                print('TIMEOUT: stopping to look for new uids.')
            elif stop_uid in uid_dict['all_uids']:
                run_condition = False
                print('FOUND stop_uid: %s -> stopping to look for new uids.'%stop_uid)
        if len(todo)<11: w=len(todo)
        else: w=11
        cdict={0:'darkgreen',1:'green',2:'forestgreen',3:'limegreen',4:'lime',5:'greenyellow',6:'yellow',7:'gold',8:'orange',9:'darkorange',10:'red',11:'darkred'}
        fig,ax=plt.subplots(figsize=(20,1.5))
        plt.barh(.1, width=w+.2, height=1, left=-.2,color=cdict[w])
        plt.xticks(ticks=[0,1,2,3,4,5,6,7,8,9,10,11], labels=[0,1,2,3,4,5,6,7,8,9,10,'>10'],fontsize=16)
        plt.xlabel('queue length for WAXS data processing',fontsize=16)
        ax.yaxis.set_visible(False);plt.xlim(-0.2,11)
        plt.tight_layout()
        display(plt.gcf())
        plt.close()
        
        ### some statistics on previously processed data:
        t_dict={}
        for p in uid_dict['processed']:
            if type(uid_dict['processed'][p]['stop']) == float: # only looking at completed uids: if processing is still running, stop is N.A.
                t_dict[uid_dict['processed'][p]['stop']]=p
        ind = (time.time()-np.array(list(t_dict.keys())))/60 <statistic_cutoff
        stats_list = sorted(np.array(list(t_dict.keys()))[ind],reverse=True)[:20]
        
        fail_count=0;success_count=0;elapsed=[];label_list=[]
        for s in stats_list:
            if uid_dict['processed'][t_dict[s]]['status']=='completed':
                elapsed.append((uid_dict['processed'][t_dict[s]]['stop']-uid_dict['processed'][t_dict[s]]['start'])/60)
                label_list.append((t_dict[s],db[t_dict[s]].start['scan_id']))
                success_count+=1
            # if uid_dict['processed'][t_dict[s]]['status'] == 'completed':
            #     success_count+=1
            elif uid_dict['processed'][t_dict[s]]['status'] == 'failed':
                fail_count+=1
                
        if success_count>0 or fail_count>0:
            fig,ax = plt.subplots(1,2,figsize=(20,7))
            plt.subplot(1,2,1)
            plt.title('status of last %s completed uids'%(success_count+fail_count),fontsize=20)
            plt.axis('off')
            pie_labels=['success','failed'];pie_size=[success_count,fail_count]
            plt.pie(pie_size,labels=pie_labels,colors=['g','r'],textprops={'fontsize': 18})

            plt.subplot(1,2,2)
            if len(elapsed) > 0:
                bbins = np.histogram(elapsed,bins=[0,5,8,10,12,14,16,18,20,24,30,60])[1] # custom spaced bins
                color_list = np.array(np.digitize(elapsed,bbins)-1,dtype=int)
                if statistic_cutoff!=None:
                    plt.title('processing time for uids completed < %s min ago'%statistic_cutoff,fontsize=20)
                plt.grid(True)
                x_tick_list=[]
                for ii,i in enumerate(elapsed):
                    plt.bar(ii,i,color=cdict[color_list[ii]])
                    x_tick_list.append('%s'%label_list[ii][1])
                plt.xlim(-1,21)
                plt.xticks(ticks=range(len(elapsed)), labels=x_tick_list,fontsize=14,rotation=45)
                plt.ylabel('WAXS processing time [min]',fontsize=20);plt.yticks(fontsize=18)
            else:
                plt.axis('off')
            plt.tight_layout()
            display(plt.gcf())
            plt.close()
        else:
            if statistic_cutoff != None:
                print('No data processing completed (failed or successful) in the past %s min...'%statistic_cutoff)
            else:
                print('No data processing completed (failed or successful) yet...')

        time.sleep(10)

 
######## check whether uids in a list can be processed as WAXS dataset  ########################################################
def check_waxs_processing_possible(uids,remove_uids=False,verbose=False):
    """
    function to check whether a uid can be processed as a WAXS dataset (criteria 1) start doc has key 'detectors' with value 'pilatus800'; 2) exit status (in stop doc) is 'success'
    uids: list of uids to be checked
    remove_uids: if True -> remove uids that cannot be processed as WAXS datasets from list of uids
    verbose: prints result for each uid: processible or not, reasons why it cannot be processed, whether uid is being removed from list
    """
    impossible_uids=[]
    for u in uids:
        processing_possible=True;reason=[]
        h=db[u]
        if 'detectors' in h.start.keys() and 'pilatus800' in h.start['detectors']: pass
        else: processing_possible=False;reason.append('WAXS detector not in list of detectors')
        if h.stop['exit_status'] != 'success': processing_possible=False;reason.append('acquisition not successfully completed')
        else: pass
        if verbose:
            if processing_possible:
                txt = colored('processing should be possible!','green');txt2='';txt3=''
            else: 
                txt = colored('processing NOT possible!','red');txt2='Reason(s): '
                for r in reason:
                    txt2+='%s, '%r
                if remove_uids:
                    txt3= colored(' -> removing uid from list to be processed','red')
            print('scan_id: %s / uid: %s -> '%(h.start['scan_id'],u),txt,txt2[:-2],txt3)
        if remove_uids and (not processing_possible):
            impossible_uids.append(u)
    if remove_uids:
        for u in impossible_uids:
            uids.remove(u)
    return uids


##### visualize queue and statistics for batch WAXS processing
def show_batch_queue_stats(stat_dict,uids,statistic_cutoff=None):
    """
    function showing queue and statistics (for successfully completed uids) during WAXS batch processing
    stat_dict: dictionary of the form {uid:{'start':time,'stop':time,'status':'failed'/'success'}}
    uids: list of uids handed to batch processing
    statistic_cutoff (float [min] or None): cutoff time for showing statistics for sucessfully processed uids
    """
    if statistic_cutoff == None:
        statistic_cutoff = np.inf
    # collect some statistic from dictionary
    finished=0;elapsed=[];x_tick_list=[];success_count=0;fail_count=0
    for s in stat_dict.keys():
        if stat_dict[s]['stop']:
            finished+=1
            if stat_dict[s]['status'] == 'success':
                success_count+=1
                if np.abs(time.time()-stat_dict[s]['stop'])<statistic_cutoff*60:
                    x_tick_list.append(str(db[s].start['scan_id']));elapsed.append((stat_dict[s]['stop']-stat_dict[s]['start'])/60)
            elif stat_dict[s]['status'] == 'failed':
                fail_count+=1
    # visualize queue
    cdict={0:'darkgreen',1:'green',2:'forestgreen',3:'limegreen',4:'lime',5:'greenyellow',6:'yellow',7:'gold',8:'orange',9:'darkorange',10:'red',11:'darkred'}
    w=min([len(uids)-finished,max(list(cdict.keys()))])
    fig,ax=plt.subplots(figsize=(20,1.5))
    plt.barh(.1, width=w+.2, height=1, left=-.2,color=cdict[w])
    plt.xticks(ticks=[0,1,2,3,4,5,6,7,8,9,10,11], labels=[0,1,2,3,4,5,6,7,8,9,10,'>10'],fontsize=16)
    plt.xlabel('queue length for batch WAXS data processing',fontsize=16)
    ax.yaxis.set_visible(False);plt.xlim(-0.2,11)
    plt.tight_layout()
    display(plt.gcf())
    plt.close()

    # visualize statistic
    if success_count>0 or fail_count>0:
        fig,ax = plt.subplots(1,2,figsize=(16,6))
        plt.subplot(1,2,1)
        plt.title('status of last %s completed uids'%(success_count+fail_count),fontsize=20)
        plt.axis('off')
        pie_labels=['success','failed'];pie_size=[success_count,fail_count]
        plt.pie(pie_size,labels=pie_labels,colors=['g','r'],textprops={'fontsize': 18})

        plt.subplot(1,2,2)
        if len(elapsed) > 0:
            bbins = np.histogram(elapsed[-20:],bins=[0,5,8,10,12,14,16,18,20,24,30,60])[1] # custom spaced bins
            color_list = np.array(np.digitize(elapsed[-20:],bbins)-1,dtype=int)
            if statistic_cutoff!=np.inf:
                plt.title('processing time for uids completed < %s min ago'%statistic_cutoff,fontsize=20)
            plt.grid(True)
            for ii,i in enumerate(elapsed[-20:]):
                plt.bar(ii,i,color=cdict[color_list[ii]])
            plt.xlim(-1,21)
            plt.xticks(ticks=range(len(elapsed[-20:])), labels=x_tick_list[-20:],fontsize=14,rotation=45)
            plt.ylabel('WAXS processing time [min]',fontsize=20);plt.yticks(fontsize=18);plt.xlabel('scan_id',fontsize=20)
        else:
            plt.axis('off')
        plt.tight_layout()
        display(plt.gcf())
        plt.close()
    else:
        if statistic_cutoff != None:
            print('No data processing completed (failed or successful) in the past %s min...'%statistic_cutoff)
        else:
            print('No data processing completed (failed or successful) yet...')
            

######################## functions related to WAXS analysis  #####################################################
def get_XPCS_from_WAXS(uid,user,cycle,verbose=False):
    """
    function to 'assign' WAXS datasets (Pilatus 800k) to the corresponding XPCS 'in-situ' dataset from 3D printing experiments
    uid: from WAXS scan for which we'd like to find the corresponding in-situ XPCS dataset
    user: user of experiment
    cycle: cycle of experiment -> need for user and cycle: need to get adjacent uids -> done by scan_id, but that one might not be unique
    returns (scan_id,uid) tuple for corresponding in-situ XPCS dataset
    """
    h=db[uid]
    waxs_end=h.stop['time']
    waxs_start=h.start['time']
    find_previous=False
    ct=1
    while not find_previous:
        (test_nr,test_uid)=get_uid_list([h.start['scan_id']-ct],user=user,cycle=cycle,uid_length=16,verbose=False)
        g=db[test_uid[0]]
        try:
            if g.start['plan_name']=='wait_for_pv' and g.start['XPCS_data']==True:
                prev_uid=g.start['uid'];prev_scan_id=g.start['scan_id'];find_previous=True
                prev_start=g.start['time'];prev_end=g.stop['time']
            else:
                ct+=1
        except:
            ct+=1
    if verbose: print('Looking at scan_id: %s    uid: %s\nprevious in-situ dataset: scan_id: %s   uid: %s'%(h.start['scan_id'],uid,prev_scan_id,prev_uid))

    find_next=False
    ct=1
    while not find_next:
        (test_nr,test_uid)=get_uid_list([h.start['scan_id']+ct],user=user,cycle=cycle,uid_length=16,verbose=False)
        g=db[test_uid[0]]
        try:
            if g.start['plan_name']=='wait_for_pv' and g.start['XPCS_data']==True:
                next_uid=g.start['uid'];next_scan_id=g.start['scan_id'];find_next=True
                next_start=g.start['time'];next_end=g.stop['time']
            else:
                ct+=1
        except:
            ct+=1
    if verbose: print('next in-situ dataset: scan_id: %s   uid: %s'%(next_scan_id,next_uid))
    if next_start<waxs_start<next_end or next_start<waxs_end<next_end or waxs_start<next_start<waxs_end or waxs_start<next_end<waxs_end:
        g=db[next_uid]
        if verbose: print('getting metadata from FOLLOWING in-situ SAXS dataset scan_id: %s -> uid: %s'%(g.start['scan_id'],next_uid))
        ref_uid=next_uid
    else: 
        ref_uid=prev_uid
        g=db[ref_uid]
        if verbose: print('getting metadata from PREVIOUS in-situ SAXS dataset scan_id: %s -> uid: %s'%(g.start['scan_id'],prev_uid))

    # check for overlap of in-situ reference dataset (XPCS) and this WAXS dataset. IF there is overlap, we assume this is an in-situ WAXS dataset
    h=db[uid]
    if max(0, min(h.stop['time'], g.stop['time']) - max(h.start['time'], g.start['time'])) >0:
        insitu_waxs = True
    else: insitu_waxs = False

    ref_md=dict(g.start)
    if verbose: print('data set is in-situ WAXS: %s'%insitu_waxs)
    
    return (g.start['scan_id'],ref_uid)



def split_array(num,original_array):
    """
    split single array into a list of a arrays
    num: number of single arrays to split 
    original_array into
    len(original_array)/num must be an integer
    """
    assert np.mod(len(original_array),num) == 0, 'ERROR: length of original array (%s) must be dividable by num (%s)'%(len(original_array),num)
    ilen=int(len(original_array)/num)
    sa=[]
    for i in range(num):
        sa.append(original_array[0+i*ilen:ilen+i*ilen])
    return sa


def waxs_fit_setup(material,amplitude_scale=1):
    """
    function to setup -material dependent- fit with mm_Voigt model of 1D WAXS data
    material: material to fit, material='?' returns list of currently available materials
    amplitude_scale: scale amplitude values in start_values; e.g. amplitude_scale=.1 might work better for crystallization onset
    returns: starting_values,bounds,peak_number, where starting_values and bounds are in the format that can be passed to mm_Voigt
    """
    material_dict={'polypropylene':
                   {'a':[10.06,11.9755312,13.16014013,15.1,15.48067536],
                    'b':[60,30,30,30,30],
                    'c':[.1,.2,.15,.45,.45],
                    'd':[.5,.5,.5,.5,.5],
                    'e':[0.01,0.01,0.01,0.01,0.01],
                    'f':[.45,0.01,0.01,0.01,0.01],
                    'g':[.7,.2,.2,.2,.2,]},
                   'polypropylene_beta':
                   {'a':[10.02,11.838,11.9748,13.1014013,15.0,15.49],
                    'b':[60,20,30,30,30,30],
                    'c':[.1,.15,.08,.15,.3,.3],
                    'd':[.5,.5,.5,.5,.5,.5],
                    'e':[0.01,0.01,0.01,0.01,0.01,0.01],
                    'f':[.45,0.0,0.0,0.0,0.0,0.0],
                    'g':[.7,.2,.2,.2,.2,.2]},
    }
    
    if material == '?':
        print('available materials: %s'%list(material_dict.keys()))
    else: 
        assert material in list(material_dict.keys()), 'ERROR: %s not in list of known materials: %s'%(material,list(material_dict.keys())) 
        if material == 'polypropylene_beta': # need tighter bounds on peak positions for split peak
            a=material_dict[material]['a'];a1=np.array(a)*.995;a1=a1.tolist();a2=np.array(a)*1.005;a2=a2.tolist()
        else:
            a=material_dict[material]['a'];a1=np.array(a)*.98;a1=a1.tolist();a2=np.array(a)*1.02;a2=a2.tolist()
        b=np.array(material_dict[material]['b'])*amplitude_scale;b=b.tolist();b1=np.zeros(len(b)).tolist();b2=np.ones(len(b))*1E4;b2=b2.tolist()
        c=material_dict[material]['c'];c1=np.array(c)*.5;c1=c1.tolist();c2=np.array(c)*2;c2=c2.tolist()
        d=material_dict[material]['d'];d1=np.zeros(len(d)).tolist();d2=np.ones(len(d)).tolist()
        e=material_dict[material]['e'];e1=np.ones(len(e))*(-1000);e1=e1.tolist();e2=np.ones(len(e))*1000;e2=e2.tolist()
        f=material_dict[material]['f'];f1=np.ones(len(f))*(-10);f1=f1.tolist();f2=np.ones(len(f))*10;f2=f2.tolist()
        g=material_dict[material]['g'];g1=np.ones(len(g))*.1;g1=g1.tolist();g2=(2*np.ones(len(g))).tolist() #only using g[0], but bounds are easier to define this way

        C=[];C+=a;C+=b;C+=c;C+=d;C+=e;C+=f;C+=g
        B1=[];B1+=a1;B1+=b1;B1+=c1;B1+=d1;B1+=e1;B1+=f1;B1+=g1
        B2=[];B2+=a2;B2+=b2;B2+=c2;B2+=d2;B2+=e2;B2+=f2;B2+=g2
        bounds=(B1,B2)
        sb1 = np.array(split_array(7,bounds[0]))
        sb2 = np.array(split_array(7,bounds[1]))
        sb2[3] = np.ones(len(sb2[3]))*2
        sb1[3] = -1*sb2[3]
        bounds_=(sb1.flatten().tolist(),sb2.flatten().tolist()) 
        pn=int(len(a)) #number of peaks
        
        return C, bounds_, pn
                   

################ functions related to creating and managing collections of XPCS and WAXS datasets  ###################################################
##### formatting panda dataframes for collection visualization
def pd_color_false(s: pd.Series) -> list[str]:
    """Helper function to format 'abc' columns.
    Args:         s: target column.
    Returns:         list of styles to apply to each target column cell.
    """
    background_colors = []
    for v in s:
        match v:
            case False:
                background_colors.append("background-color: red")
            case True:
                background_colors.append("background-color: green")
    return background_colors

def pd_color_warning(s: pd.Series) -> list[str]:
    """Helper function to format 'abc' columns.
    Args:         s: target column.
    Returns:       list of styles to apply to each target column cell.
    """
    background_colors = []
    for v in s:
        match v:
            case False:
                background_colors.append("background-color: yellow")
            case True:
                background_colors.append("background-color: green")
            case '':
                pass
            case _:
                pass
    return background_colors

def pd_color_true(s: pd.Series) -> list[str]:
    """Helper function 
    Args:         s: target column.
    Returns:         list of styles to apply to each target column cell.
    """
    background_colors = []
    for v in s:
        match v:
            case False:
                background_colors.append("background-color: green")
            case True:
                background_colors.append("background-color: red")
    return background_colors

def pd_color_timing(s: pd.Series) -> list[str]:
    """Helper function 
    Args:         s: target column.
    Returns:       list of styles to apply to each target column cell.
    """
    background_colors = []
    for v in s:
        match v:
            case 'OK':
                background_colors.append("background-color: green")
            case 'ok-ish':
                background_colors.append("background-color: yellow")
            case 'WARNING':
                background_colors.append("background-color: red")
    return background_colors

def collection_style(df: pd.DataFrame) -> Styler:
    """Function to style whole dataframe.
    Args: df: target dataframe.
    Returns: styled dataframe.
    """
    styler = df.style
    for col in df.columns:
        match df[col].name:
            case "timing":
                     styler = styler.apply(pd_color_timing, subset=col)
            case "XPCS exit status":
                    styler = styler.apply(pd_color_false, subset=col)
            case "WAXS exit status":
                    styler = styler.apply(pd_color_false, subset=col)
            case "md error":
                    styler = styler.apply(pd_color_true, subset=col)
            case "XPCS processed":
                    styler = styler.apply(pd_color_warning, subset=col)
            case "WAXS processed":
                    styler = styler.apply(pd_color_warning, subset=col)
            case _:
                pass
    return styler

def styled_df(df):
    styled_df = collection_style(df)
    return styled_df.format(precision=1).format(subset=['beam position relative to platform'], precision=3)

def color_warning_report(val):
    return f'color: {"red" if val==2 else ("yellow" if val==1 else "black")}'




def load_collection_database(name,path):
    """
    loads collection_database stored as json file
    name: name of json file (either with or without file extension)
    path: full path to json file
    returns: data_base_loaded, dictionary with collection, panda.DataFrame with searchable metadata and collection information -> data_base_loaded: True/False
    """
    name=name.split('.')[0]
    #path+name+'.json' #just in case file ending had been included in the filename
    if os.path.isfile(path+name+'.json'):

        print(colored('Found existing database %s!'%(path+name+'.json'),'green'))
        inp=input('\nLoad existing database and append? [y,n]:')

        if inp in ['y','Y','yes','Yes','YES']:
            print('-> loading database...')
            f = open (path+name+'.json', "r")
            data_tmp = json.loads(f.read()) 
            f.close()
            df_sum = pd.DataFrame.from_dict(data_tmp['panda_dict'])
            col_dict=data_tmp['collection_dict']
            data_base_loaded = True
        else:
            print(colored('-> creating new database...no worries, existing database will be backed up when saving to file!','yellow'))
            data_base_loaded = False
            col_dict={};df_sum={}
    else: 
        print(colored('no database found for %s%s -> creating a new one!'%(path,name),'yellow'))
        data_base_loaded = False
        col_dict={};df_sum=pd.DataFrame({})
    return col_dict, df_sum

                                           
def save_collection_database(name, path, col_dict, df_sum):
    """
    function to save col_dict and df_sum in one json file as database
    IF file already exists: existing file will get a timestamp and moved to a database backup directory
    name: name of database (json file,; works with and without .json)
    path: full path for saving database
    col_dict: current version of collection dictionary
    df_sum: current version of panda DataFrame (will be converted to dict and stored in same json file as col_dict)
    """
    name=name.split('.')[0]
    pd_dict_ = pd.DataFrame.to_dict(df_sum)
    if os.path.isfile(path+name+'.json'):
        add_string=''
        for i in time.ctime(time.time()).split(' ')[2:]:
            add_string+='_'+i
        print(colored('Database file already exists...saving backup with timestamp in %sXPCS_WAXS_database_backups/  as %s.json before overwriting existing file!'%(path,name+add_string),color='yellow'))
        if not os.path.isdir(path+'XPCS_WAXS_database_backups/'):
            os.mkdir(path+'XPCS_WAXS_database_backups/',0o777)
            print('Backup directory does not exist...creating it!')
        os.rename(path+name+'.json', path+'XPCS_WAXS_database_backups/'+name+add_string+'.json')

    save_dict={'panda_dict':pd_dict_,'collection_dict':col_dict}
    with open('%s%s.json'%(path,name), "w") as outfile:
        json.dump(save_dict, outfile)
    print(colored('Saved database as %s%s.json!'%(path,name),color='green'))

    
def show_oav_images_report(uid_list,start_times=None,plot_dict={},verbose=False):
    """
    uid_list: list of uids to plot OAV images from
        oav_mode = single -> plots one image
        oav_mpde = 'start_end' -> plots two images
        oav_mode = 'movie' or 'movie_max' -> plots first and last image
        start_times: if not None: list of start times for datasets to put images on a continuous timescale; if provided, start_times must be a list of same length as uid_list
        plot_dict: dictionary with parametes for the plot
            'y_extend':[200,300] -> limit plot in vertical direction to +200/-300 pixel from direct beam position (ignored of 'cross':None)
            'cross':[200,400] -> x,y position of direct beam
            'sc_bw': width of scale bar in um
            'cw': width of cross marking direct beam position [pixels]
    """
    
    # ensure start_times -if provided- is a list of same length as uid_list:
    if start_times != None:
        assert len(uid_list) == len(start_times), 'ERROR: start_times must be None or a list of start times the same length as uid_list!'
    else: start_times=np.zeros(len(uid_list)).tolist()
    # get number of panels needed:
    pn=0
    for u in uid_list:
        md=get_meta_data(u,verbose=False)
        if md['OAV_mode'] == 'single':
            pn+=1
        elif md['OAV_mode'] in ['start_end','movie','movie_max']:
            pn+=2
            
    y_extend=None; cx=None; cy=None; sc_bw=200; cw=200
    if 'y_extend' in plot_dict.keys():
        y_extend = plot_dict['y_extend']
    if 'cross' in plot_dict.keys():
        cx=plot_dict['cross'][0];cy=plot_dict['cross'][1]
    if 'sc_bw' in plot_dict.keys():
        sc_bw = plot_dict['sc_bw']
    if 'cw' in plot_dict.keys():
        cw = plot_dict['cw'] 
        
    nrows=int(np.ceil(pn/4))
    fig,ax = plt.subplots(nrows,ncols=4,figsize=(20,4))

    detector='OAV_image'
    pc=1
    for uu,u in enumerate(uid_list):
        h=db[u];md=get_meta_data(u,verbose=False)
        if md['OAV_mode'] == 'single':
            li=[0];to=np.array([0])+start_times[uu]
        elif md['OAV_mode'] in ['start_end','movie','movie_max']:
            oav_acquire_period = h['descriptors'][1]['configuration']['OAV']['data']['OAV_cam_acquire_period']
            oav_num_images = h['descriptors'][1]['configuration']['OAV']['data']['OAV_cam_num_images']
            li=[0,-1];to=np.array([0,oav_num_images*oav_acquire_period])+start_times[uu]
        dimg = h.xarray_dask()[detector][0]
        dimg = dask.array.rot90(dimg, axes=(2, 1))
        for ll,l in enumerate(li):
            plt.subplot(nrows,4,pc)
            plt.imshow(dimg[l]);pc+=1
            #plt.axis('equal')
            plt.axis('off')
            plt.title('scan_id: %s\nt=%.2fs'%(md['scan_id'],to[ll]))
            if cx != None:
                plt.plot([cx-cw/2,cx+cw/2],[cy,cy],'r-',alpha=.5)
                plt.plot([cx,cx],[cy-cw/2,cy+cw/2],'r-',alpha=.5)
            else:
                cy=np.shape(dimg[0])[1]/2 # not plotting a cross, but taking center of the image as reference for y_extend, if provided
            if y_extend != None:
                try:
                    sc_b=sc_bw/md['OAV_resolution [um_pixel]']
                    plt.plot([np.shape(dimg)[2]-500,np.shape(dimg)[2]-500+sc_b],[cy-y_extend[0]+150,cy-y_extend[0]+150],'r-',linewidth=5)
                    plt.text(np.shape(dimg)[2]-600,cy-y_extend[0]+30,'%s $\mu$m'%int(sc_b*md['OAV_resolution [um_pixel]']),color='r',fontsize=12)
                except:
                    if verbose: print('could NOT find scalebar information for uid %s'%u)
                plt.ylim([max([cy-y_extend[0],0]),min([np.shape(dimg[0])[1],cy+y_extend[1]])])
            else:
                try:
                    sc_b=sc_bw/md['OAV_resolution [um_pixel]']
                    plt.plot([np.shape(dimg)[2]-500,np.shape(dimg)[2]-500+sc_b],[200,200],'r-',linewidth=5)
                    plt.text(np.shape(dimg)[2]-600,30,'%s $\mu$m'%int(sc_b*md['OAV_resolution [um_pixel]']),color='r',fontsize=12)
                except:
                    if verbose: print('could NOT find scalebar information for uid %s'%u)
    plt.tight_layout()       


def collection_report(uuid,collection_dict,df_sum=None,md_list=None,accuracy_list=None,timelineplot=False,show_oavs=False,plot_dict={},verbose=False):
    """
    Provide a detailed report on all datasets within a collection
    uuid: collection uid
    collection_dict: dictionary containing detailed information about all individual datasets in all collections
    sum_df: optional, current sum_df to show summary of collection in addition to report on individual uids within this collection
    md_list / accuracy_list: optional, if provided color codes problems with data that exceeds tolerances for certain metadata to be considered as 'same', i.e. same experimental conditions within one collection; length of both lists must match
    timelineplot: if True -> provide a visualization of the timing between all datasets in the collection
    show_oavs: show oavs that might have been collected with XPCS data (if more than one per uid: shows first and last)
    plot_dict: dictionary with arguments for "show_oav_images_report" -> see doc string of "show_oav_images_report" for details
    returns: panda DataFrame with detailed report, color codes errors and warnings if md_list and accuracy_list are provided, displays sum_df (if provided) for same collection uid 
    """
    c = collection_dict[uuid]
    md_list=list(c.keys())
    for i in ['data','md_warning_list']:
        md_list.remove(i)

    pd_dict={};start_times = [];stop_times=[];id_list=[];xpcs_uid_list=[]
    for dd,d in enumerate(c['data']['XPCS'].keys()):
        md_ = get_meta_data(d,verbose=False)
        xpcs_uid_list.append(d)
        id_list.append(c['data']['XPCS'][d]['scan_id'])
        pd_dict[d]={'scan_id':c['data']['XPCS'][d]['scan_id'],'data type':'XPCS','exit_status':c['data']['XPCS'][d]['exit_status'],'data processed':c['data']['XPCS'][d]['data processed']}
        start_times.append(c['data']['XPCS'][d]['start']);stop_times.append(c['data']['XPCS'][d]['stop'])
        for m in md_list:
            pd_dict[d][m]=c[m][dd]
        pd_dict[d]['data acquisition']='%ss x %sfr, T= %.2E'%(md_['acquire period'],md_['number of images'],Decimal(md_['transmission']))

    wstart_times = []; wstop_times=[]; wid_list=[]
    for dd,d in enumerate(c['data']['WAXS'].keys()):
        h=db[d]
        wid_list.append(c['data']['WAXS'][d]['scan_id'])
        pd_dict[d]={'scan_id':c['data']['WAXS'][d]['scan_id'],'data type':'WAXS','exit_status':c['data']['WAXS'][d]['exit_status'],'data processed':c['data']['WAXS'][d]['data processed']}
        pd_dict[d]['data acquisition'] = '%.3fs x %s fr'%(h.start['pil800k_acquire_period'],h.start['pil800k_imnum'])
        wstart_times.append(c['data']['WAXS'][d]['start']);wstop_times.append(c['data']['WAXS'][d]['stop'])
    
    toff=min(start_times+wstart_times)
    report_df=pd.DataFrame.from_dict(pd_dict)
    
    #### check for idle gaps between datasets:
    start = np.array(start_times+wstart_times)-toff
    stop = np.array(stop_times+wstop_times)-toff
    time_res=.2
    t=np.arange(0,np.max(stop),time_res)
    timeline=[]
    for i in range(len(stop)):
        x=np.zeros(len(t))
        ind1=t>=start[i];ind2=t<=stop[i]
        x[ind1*ind2]=1
        timeline.append(x)
    ttline=np.sum(timeline,axis=0)
    groups = [];keys = []
    for k, g in groupby(ttline):
        groups.append(list(g))      # Store group iterator as a list
        keys.append(k)
    gaps=[]
    for kk,k in enumerate(keys):
        if k ==0.:
            gaps.append(len(groups[kk])*time_res)
    gaps_thresh={0:'green',10:'yellow',30:'red'}
    if len(gaps)==0:
        gap_keys=[0]
    else:
        gl=list(gaps_thresh.keys());gap_keys=[]
        for g in gaps:
            ind=np.array(gl)-g>=0
            if max(ind) < 1: # this is a gap out of scale
                gap_keys.append(gl[len(gl)-1])
            else: # gap is within the range
                gap_ind=np.argmax(ind);gap_ind=max([0,gap_ind-1]);gap_keys.append(gl[gap_ind])
    estr=''
    if max(gap_keys)>0:
        estr='WARNING: '
    if not timelineplot:
        print(colored(estr+'Idle gaps between individual XPCS/WAXS datasets are [s]: %s'%gaps,gaps_thresh[max(gap_keys)]))

    
    if timelineplot:
        fig,ax=plt.subplots(figsize=(20,2))
        for i in range(len(start_times)):
            plt.barh(1.5, width=stop_times[i]-start_times[i], height=1, left=start_times[i]-toff,color='C%s'%i)
            plt.text(start_times[i]-toff+0.5*(stop_times[i]-start_times[i]),1.3,id_list[i],horizontalalignment='center',fontsize=14)
        for i in range(len(wstart_times)):
            plt.barh(0, width=wstop_times[i]-wstart_times[i], height=1, left=wstart_times[i]-toff,color='C%s'%i)
            plt.text(wstart_times[i]-toff+0.5*(wstop_times[i]-wstart_times[i]),-.2,wid_list[i],horizontalalignment='center',fontsize=14)
        plt.xlim(left=-2);plt.xlabel('time [s]');plt.title('timing between datasets')
        plt.text(0,2.4,estr+'Idle gaps between individual XPCS/WAXS datasets are [s]: %s'%gaps,color=gaps_thresh[max(gap_keys)],fontsize=12)
        plt.yticks(ticks=[0,1.5], labels=['WAXS','XPCS'],fontsize=12)
        ax=plt.gca();ax.set_axisbelow(True);plt.grid(True)
        plt.tight_layout()
    
    if show_oavs:
        show_oav_images_report(xpcs_uid_list,start_times=(np.array(start_times)-toff).tolist(),plot_dict=plot_dict,verbose=False)
    
    # Get detailed information about data processing / analysis that has been done on the individual uids   
    analysis_dict={}
    for d_type in ['XPCS','WAXS']:
        for u in c['data'][d_type].keys():
            analysis_dict[u]={}
            for a in c['data'][d_type][u]['analysis'].keys():
                a_list=[]
                for l in c['data'][d_type][u]['analysis'][a]:
                    if '_Res.h5' in l: # currently only looking for XPCS processing, can expand for further analysis later, probably will be looking at .pkl with specific filename pattern then
                        a_list.append(l.split('_Res.h5')[-2].split(u)[-1])
                    if 'waxs_analysis' in l and '.pkl' in l:
                        a_list.append(l.split('_uid')[0].split(u+'/')[-1])
                analysis_dict[u][a]=a_list
                
    header={};analyst_list=[]
    for a in analysis_dict.keys():
        header[a]='  '
        analyst_list+=(list( analysis_dict[a].keys()))
    header_df = pd.DataFrame(header,index=['analysis / processing by:             '])
    analyst_list=sorted(list(set(analyst_list)))
    
    for aa,a in enumerate(analyst_list):
        ana_dict={}
        for u in analysis_dict.keys():
            try:
                sstr=''
                for o in analysis_dict[u][a]:
                    sstr+=o+', '
                ana_dict[u] = sstr[:-2]
            except:
                ana_dict[u]='-'
        ana_df = pd.DataFrame(ana_dict,index=[a]) 
        if aa==0:
            ana_dfsum=ana_df
        else:
            ana_dfsum = pd.concat( [ana_dfsum,ana_df],ignore_index=False)
    
    report_df=pd.concat( [report_df,header_df],ignore_index=False)
    report_df=pd.concat( [report_df,ana_dfsum],ignore_index=False)
        
    report_df.replace(to_replace=np.nan,value='-',inplace=True)
    pd.set_option('display.max_colwidth', None)
    
    try:
        if df_sum ==None:
            pass
    except:
        print(colored('report for collection uid: %s\n'%uuid,color="green"))
        display(styled_df(df_sum[df_sum['col_uid']==uuid]))
    
    print(colored('\nreports for individual datasets in collection %s:\n'%uuid,color="green"))
    # check for problems within collection, i.e. mismatched md
    if md_list != None and accuracy_list!=None:
        assert len(md_list) == len(accuracy_list), "ERROR: md_list and accuracy_list need to have the same length...skip color-coding potential md issues! md_list: %s, accuracy_list: %s"%(md_list,accuracy_list)       
        mask = pd.DataFrame(0, index=report_df.index, columns=report_df.columns) # create empty mask
        # exact matches required, i.e. corresponding element in accuracy_list is 'None'
        for k in np.array(md_list)[np.array(accuracy_list)==None]:
            x=np.array(report_df.loc[k])[np.array(report_df.loc[k])!='-'].tolist()
            if len(set(x)) >1:
                mask.loc[k]=2 # 2 corresponds to error level, 1 would be a warning
        # match within tolerance required: indicate a warning (1) when exceeding half the tolerance value and 'error' (2) when exceeding tolerance (all with respect to mean of all data)
        for kk,k in enumerate(np.array(md_list)[np.array(accuracy_list)!=None]):
            x=np.array(report_df.loc[k])[np.array(report_df.loc[k])!='-']
            tol=np.array(accuracy_list)[np.array(accuracy_list)!=None][kk]
            if sum(np.abs(x-np.mean(x))>tol/2) > 0:
                mask.loc[k]=1
            elif sum(np.abs(x-np.mean(x))>tol) > 0:
                mask.loc[k]=2
        print(colored('WARNING: md - <md> > tol/2',color="yellow"))
        print(colored('ERROR: md - <md> > tol',color="red"))
        display(report_df.style.apply(lambda _: mask.map(color_warning_report), axis=None).format(precision=3))
    else:
        display(report_df)        
    return report_df


def add_datasets_to_database(uids,col_dict,df_sum,_base_path_,md_list,accuracy_list,remove_duplicates=False):
    """
    function to add datasets to collection database (given as list of uids)
    uids: list of uids to be added
    col_dict: current version of collection dictionary
    df_sum: current version of panda DataFrame 
    _base_path_: full path up to /cycle/user/Results/...
    md_list: list with metadata keys that should be searchable, i.e. they will become columns in the panda DataFrame
    accuracy_list: list of tolerances to accept metadata entries as equal; None is equivalent to exact match required. Length must match that of md_list
    remove_duplicates: if True: remove duplicates in database. We keep the FIRST entry to presevere the collection uid
    """
    meta_data_sets=[];waxs_data_sets=[]
    try: del tmp_mds,tmp_waxs
    except: pass
    print('Datasets to be added to the collection: ')
    for u in uids:
        h=db[u]
        if 'XPCS_data' in list(h.start.keys()) and h.start['XPCS_data']:
            dataset_type='XPCS';measurement = h.start['Measurement']
            if 'in-situ series' in h.start['Measurement']:
                try: # this will fail for the first round when there is nothing to append
                    meta_data_sets.append(tmp_mds)
                except: pass
                tmp_mds=[(h.start['scan_id'],u)]
            else:  
                try: tmp_mds.append((h.start['scan_id'],u))
                except: pass
        elif 'detectors' in  list(h.start.keys()) and h.start['detectors']==['pilatus800']:
            dataset_type='WAXS';measurement = '%.3fs x %s fr'%(h.start['pil800k_acquire_period'],h.start['pil800k_imnum'])
            try: # this will fail for the first round when there is nothing to append
                    waxs_data_sets.append(tmp_waxs)
            except: pass
            tmp_waxs=[(h.start['scan_id'],u)]
        else: dataset_type='unknown'
        print('scan_id: %s   uid: %s  data type: %s   %s'%(h.start['scan_id'],u,dataset_type,measurement))

    meta_data_sets.append(tmp_mds)
    waxs_data_sets.append(tmp_waxs)
    
    #for mm,m in enumerate(meta_data_sets):
    print(' ')
    for mm in tqdm (range(len(meta_data_sets)),desc="Adding collections of uids to database…",  ascii=False, ncols=200,file=sys.stdout, colour='GREEN'):
        m=meta_data_sets[mm]
        
        ### end modif for progressbar
        col_uid = col_uid=uuid.uuid4().hex
        #print('meta_data_set #%s:\n%s\n\n'%(mm,m))
        col_dict[col_uid]={'data':{'XPCS':{},'WAXS':{}}};pd_dict={};md_warning_list=[];data_error=[];processing_complete=[]
        pd_dict['col_uid']=[col_uid]
        pd_dict['XPCS data']='';pd_dict['WAXS data']=''
        for n in m:
            h=db[n[1]]  # until we go to pre-arm the detector, the start for XPCS is pretty correct, but stop might be delayed by file processing -> calculate 'stop' as end of data acquisition from start, number of frames and acquire period
            col_dict[col_uid]['data']['XPCS'][n[1]]={'scan_id':n[0],'start':h.start['time'],'stop':h.start['time']+float(h.start['acquire period'])*float(h.start['number of images']),'exit_status':h.stop['exit_status']}
            pd_dict['XPCS data']+='%s, '%n[0]
            col_dict[col_uid]['data']['XPCS'][n[1]]['data processed']= (len(glob.glob(r'%s%s/%s/Results/%s/*.h5'%(_base_path_,h.start['cycle'],h.start['user'],h.start['uid']))) > 0)
        pd_dict['XPCS data']=pd_dict['XPCS data'][:-2]
        for i in md_list:
            col_dict[col_uid][i]=[]
        for l in range(len(m)):
            h=db[m[l][1]]
            for i in md_list:
                col_dict[col_uid][i].append(h.start[i])
        for ii,i in enumerate(md_list):
            if not accuracy_list[ii]: # this is a text entry like 'sample' where we cannot accept any deviations across the collection
                if len(set(col_dict[col_uid][i]))>1:
                    raise Exception('ERROR: this collection of uids contains metadata that cannot be merged: %s'%list(set(col_dict[col_uid][i])))
                else: pd_dict[i] = list(set(col_dict[col_uid][i]))[0]
            else:
                if len(set(col_dict[col_uid][i]))>1:
                    if any(np.abs(np.array(list(set(col_dict[col_uid][i])))-np.mean(np.array(list(set(col_dict[col_uid][i]))))) > accuracy_list[ii]):
                        md_warning_list.append([(i,accuracy_list[ii])])
                    pd_dict[i]=np.mean(col_dict[col_uid][i])
                elif len(set(col_dict[col_uid][i])) == 1:
                    pd_dict[i]=col_dict[col_uid][i][0]
        col_dict[col_uid]['md_warning_list']=md_warning_list
        pd_dict['md error']=len(md_warning_list)>0

        data_processing=True;data_status=True
        for k in col_dict[col_uid]['data']['XPCS'].keys():
            if col_dict[col_uid]['data']['XPCS'][k]['exit_status']!= 'success': data_status=False
            data_processing*=col_dict[col_uid]['data']['XPCS'][k]['data processed']
        pd_dict['XPCS processed']=bool(data_processing)
        pd_dict['XPCS exit status']=bool(data_status)

        # include the WAXS data:
        pd_waxs_data='';waxs_data_processing=True;ct=0
        for w in waxs_data_sets:
            ref_uid = get_XPCS_from_WAXS(w[0][1],h.start['user'],h.start['cycle'],verbose=False)
            if ref_uid[1] in col_dict[col_uid]['data']['XPCS'].keys():
                ct+=1
                pd_waxs_data+='%s, '%(w[0][0])
                g=db[w[0][1]]
                d_proc = (len(glob.glob(r'%s%s/%s/Results/%s/waxs_analysis*.pkl'%(_base_path_,g.start['cycle'],g.start['user'],g.start['uid']))) > 0)
                # similar as for XPCS: start is ok, but stop is delayed by data transfer -> calculate
                col_dict[col_uid]['data']['WAXS'][w[0][1]]={'scan_id':g.start['scan_id'],'start':g.start['time'],'stop':g.start['time']+g.start['pil800k_acquire_period']*g.start['pil800k_imnum'],'exit_status':g.stop['exit_status'],'data processed':d_proc}
                waxs_data_processing*=d_proc

        #waxs_processing=True
        waxs_data_status=True
        for k in col_dict[col_uid]['data']['WAXS'].keys():
            if col_dict[col_uid]['data']['WAXS'][k]['exit_status']!= 'success': waxs_data_status=False
            #data_processing*=col_dict[col_uid]['data']['XPCS'][k]['data processed']

        if ct == 0: 
            pd_dict['WAXS processed']=False
        else:
            pd_dict['WAXS processed']=bool(waxs_data_processing)

        pd_dict['WAXS exit status']=bool(waxs_data_status)
        pd_dict['WAXS data']=pd_waxs_data[:-2]

        ### at this point we should have all uids for each collection -> can check for timing
        c = col_dict[col_uid]    

        start_times = [];stop_times=[]
        for d_type in ['XPCS','WAXS']:
            for dd,d in enumerate(c['data'][d_type].keys()):       
                start_times.append(c['data'][d_type][d]['start']);stop_times.append(c['data'][d_type][d]['stop'])

        toff=min(start_times)    
        #### check for idle gaps between datasets:
        start = np.array(start_times)-toff
        stop = np.array(stop_times)-toff
        time_res=.2
        t=np.arange(0,np.max(stop),time_res)
        timeline=[]
        for l in range(len(stop)):
            x=np.zeros(len(t))
            ind1=t>=start[l];ind2=t<=stop[l]
            x[ind1*ind2]=1
            timeline.append(x)
        ttline=np.sum(timeline,axis=0)
        groups = [];keys = []
        for k_, g in groupby(ttline):
            groups.append(list(g))      # Store group iterator as a list
            keys.append(k_)
        gaps=[]
        for kk_,k_ in enumerate(keys):
            if k_ ==0.:
                gaps.append(len(groups[kk_])*time_res)
        gaps_thresh={0:'OK',10:'ok-ish',30:'WARNING'}
        if len(gaps)==0:
            gap_keys=[0]
        else:
            gl=list(gaps_thresh.keys());gap_keys=[]
            for g in gaps:
                ind=np.array(gl)-g>=0
                if max(ind) < 1: # this is a gap out of scale
                    gap_keys.append(gl[len(gl)-1])
                else: # gap is within the range
                    gap_ind=np.argmax(ind);gap_ind=max([0,gap_ind-1]);gap_keys.append(gl[gap_ind])
        estr=gaps_thresh[max(gap_keys)]
        pd_dict['timing']=gaps_thresh[max(gap_keys)]
        ###################### end of timing check @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

        # generate or append panda dataframe
        df=pd.DataFrame.from_dict(pd_dict)
        df_sum=pd.concat([df_sum, df], sort=False, ignore_index=True)
    
    if remove_duplicates:
        df_sum.drop_duplicates(subset=['XPCS data','WAXS data']+md_list, keep='first', inplace=True, ignore_index=True)
        current_keys = list(col_dict.keys())
        for re in current_keys:
            if re not in list(df_sum['col_uid']):
                del col_dict[re]
        print(colored('\nremoved duplicates from DataFrame and collection dictionary',color='green'))
    return col_dict,df_sum


def update_processing_analysis(uids,col_dict,df_sum,name_list,_base_path_):
    """
    update or create detailed information about data processing/analyis for a (set of) uid(s) and a list of user names
    updates both individual uis in col_dict aggregate information in df_sum
    uids: single uid or list of uids to update
    col_dict: current version of collection dictionary
    df_sum: current version of aggregate DataFrame
    name list: combined list of user(s) and analysts who might have processed or analyzed data
    _base_path_: full path up to /cycle/user/Results/...
    returns: updated versions of col_dict and df_sum
    """
    if type(uids) == str:
        uids=[uids]
        
    for tq in tqdm (range(len(uids)),desc="Updating uids in database…",  ascii=False, ncols=200,file=sys.stdout, colour='GREEN'):
    #for u in uids:
        u=uids[tq]
        h=db[u]
        try:
            h.start['XPCS_data']
            d_type='XPCS'
        except:
            try:
                h.start['detectors']
                d_type='WAXS'
            except:
                raise Exception('ERROR for uid: %s-> could NOT figure out whether this is XPCS or WAXS data...'%u)
         ## need to get a pointer to col_dict, need to upate ALL entries containing this uid in the end!!!
        col_uids = list(df_sum['col_uid'][df_sum['%s data'%d_type].str.contains('%s'%h.start['scan_id'])]) # this is a list of all collection_uids that contain the current uid (as judged by scan_id, result goes into col_dict by uid -> use try/except in case scan_id was not unique)

        analysis_dict={}
        for p in name_list:
            res_dict = _base_path_+'%s/%s/Results/%s/'%(h.start['cycle'],p,u)
            if os.path.isdir(res_dict):
                if d_type == 'XPCS':
                    f_list = glob.glob(r'%s*.h5'%res_dict)
                    an_tmp=[]
                    for f in f_list:
                        an_tmp.append(f)
                        #an_tmp.append(f.split('uid=%s'%u)[1].split('_Res.h5')[0]) # -> can have full information in col_dict
                elif d_type == 'WAXS':
                    f_list = glob.glob(r'%swaxs_analysis*.pkl'%res_dict)
                    an_tmp=[]
                    for f in f_list:
                        an_tmp.append(f)
                        #an_tmp.append(f.split('%s'%res_dict)[1].split('_uid')[0]) #-> can have full information in col_dict

                if len(an_tmp)>0:
                    analysis_dict[p]=an_tmp
        for cu in col_uids:
            try:
                col_dict[cu]['data'][d_type][u]['analysis']=analysis_dict
            except:
                print('ooops, scan_id was not unique, skip this one!')
            # while we're here: update 'data processed' if necessary and update the data frame as well
            if len(analysis_dict.keys())> 0:# and (not col_dict[cu]['data'][d_type][u]['data processed']):
                col_dict[cu]['data'][d_type][u]['data processed']=True
            else:
                col_dict[cu]['data'][d_type][u]['data processed']=False
    
    # update aggregate info in DataFrame
    for cu in col_dict.keys():
        for d in ['XPCS','WAXS']:
            processed=True
            if len(col_dict[cu]['data'][d].keys()) == 0:
                processed = False
            for s in col_dict[cu]['data'][d].keys():
                processed*=bool(col_dict[cu]['data'][d][s]['data processed'])
            df_sum.loc[df_sum['col_uid']==cu,'%s processed'%d]=bool(processed)
    return col_dict,df_sum

#######################   SEARCH DATABASE ###################################################################
def find_char(s, ch):
    """
    helper function: find all indicies of a character ch in the string s
    """
    return [i for i, ltr in enumerate(s) if ltr == ch]


def search_pd_database(df_sum,search,verbose=False):
    """
    parser to perform search on a pd.DataFrame in a unified fashion, including logic operations
    example of search string: search="((`HOM O` AND '999') OR 'PPMA') in 'sample' & 'magigoo' in 'substrate' & 110 < 'printbed temperature' <=120 & ('OK' OR 'ok-ish') in 'timing'  & 'md error' == False"
    Notice:
        - search strings or column names containing white spaces must use backticks ` ` instead of regular ticks ''
        - search within a column can contain AND and OR (NOT is not implemented...), while logic involving different columns can only be &
        - searching for strings with white spaces is implemented but not thoroughly tested: avoid white spaces when searching for strings, if possible
    df_sum: current version of panda DataFrame that serves as database index
    search: str, search string, see above for example
    returns: dict with 
            - 'search string': search
            - 'logic list': bolean, mask for each individual column search 
            - 'index mask': boolean, index of rows that fulfill all search criteria
            - 'filtered collection uids': list of collection uids that fulfill all search criteria
    """
    # create dictionary that maps column names into strings that can be passed to query (column names with white space need `...` to be recognized as a continuous string)
    scn = {}
    for i in list(df_sum.columns):
        scn[i]={'query name':'`'+i+'`','dtype':type(df_sum[i][0])}
    
    logic_list=[]
    s=search.split('&') # we only allow & in the global search string, no OR
    for c in s:
        if verbose:
            print('\n')
        if ' in ' in c:            
            search_column=c.split(' in ')[-1].split("'")[1] # column we're going to do the search on
            if verbose:
                print('%s: this ia an "in" case!'%c)
                print('we are going to search column "%s"!'%search_column)
            assert search_column in list(df_sum.columns), 'ERROR: %s is not a valid key for this dataset!'%search_column
            stup=c.split(' in ')[0] # potential tuple that defines the search
            if 'OR' in stup or 'AND' in stup:
                if verbose: print('gonna make replacements and use eval!')
                stup_=stup
                for k in ["(",")","AND","OR"]:
                    stup_=stup_.replace(k,'')
                try:
                    stup_.split("'").remove('')
                except:
                    pass
                try:
                    stup_.split('`').remove('')
                except:
                    pass
                patternlist=[]
                if '`' in stup_:
                    if verbose: print('search pattern includes white spaces!')
                    h=find_char(stup_,'`')
                    assert np.mod(len(h),2)==0, 'ERROR: found unbalanced number of backticks...'  
                    for i in range(int(len(h)/2)):
                        patternlist.append(stup_[h[2*i]:h[2*i+1]].replace("`",""))
                        stup_=stup_.replace("`%s`"%patternlist[-1],"")
                    #stup_=stup_.replace(" ","").split("'")
                for ii,i in enumerate(patternlist):
                    if ' ' in i:
                        patternlist[ii] = '`'+i+'`'
                stup_=stup_.replace(" ","").split("'")
                for i in stup_:
                        if i!='' and i !="":
                            patternlist.append(i)
                patternlist
                if scn[search_column]['dtype']==str:
                    for p in patternlist:
                        rep = 'df_sum["%s"].str.contains("%s")'%(search_column,p)
                        stup=stup.replace(p,rep)
                elif scn[search_column]['dtype'] in [int, float,np.int64, np.int32, np.float32, np.float64]:
                    print(colored('Logical comparison with numerical data type, like (120 OR 80) in "column", is currently NOT implemented',color='red'))
                stup=stup.replace("AND","&")
                stup=stup.replace("OR","|")
                stup=stup.replace("\'","")
                logic_list.append(eval(stup))           
            elif not 'OR' in stup and not 'AND' in stup:
                if verbose: print('this is simple, just one value to check!')
                if '`' in stup:
                    if verbose: print('containing white spaces')
                    pp=stup.split('(')[-1].split(')')[0]
                    h=find_char(pp,'`')
                    search_pattern = pp[h[0]:h[1]+1]
                else:
                    search_pattern=stup.split('(')[-1].split(')')[0].replace(' ','')
                if scn[search_column]['dtype']==str:
                    rep = 'df_sum["%s"].str.contains("%s")'%(search_column,search_pattern)
                elif scn[search_column]['dtype'] in [int, float,np.int64, np.int32, np.float32, np.float64]:
                    if 'float' in str(scn[search_column]['dtype']):
                        search_pattern=np.float64(search_pattern)
                        x=str(search_pattern).split('.')
                        len(x[1])
                        rep = 'df_sum["%s"]==%.14f'%(search_column,search_pattern)
                    else: 
                        search_pattern=np.int64(search_pattern)
                        rep = 'df_sum["%s"]==%i'%(search_column,search_pattern)
                rep=rep.replace("\'","")
                logic_list.append(eval(rep))

        if '<' in c or '>' in c or '==' in c:
            if verbose: print('%s: simple comparison...'%c)
            for k in scn.keys():
                if k in c:
                    search_column=scn[k]['query name']
                    key=k
            stup=c
            stup_=stup.replace(key,search_column)
            stup_=stup_.replace("'","")  
            ll=np.zeros(len(list(df_sum.index)),dtype=bool)
            for i in list(df_sum.query(stup_).index):
                ll[i]=True
            logic_list.append(ll)

        loglist = np.array(logic_list,dtype=bool)
        for i in range(len(loglist)):
            if i ==0:
                index_mask = loglist[i]
            else:
                index_mask=index_mask & loglist[i]
                
    filtered_col_uids=df_sum[index_mask]['col_uid']
    search_results={'search string':search,'logic list':logic_list,'index mask':index_mask,'filtered collection uids':filtered_col_uids}

    return search_results



def waxs_fit_setup2(material,amplitude_scale=1):
    """
    function to setup -material dependent- fit with mm2_Voigt model of 1D WAXS data
    material: material to fit, material='?' returns list of currently available materials
    amplitude_scale: scale amplitude values in start_values; e.g. amplitude_scale=.1 might work better for crystallization onset
    returns: starting_values,bounds, bounds_gop ,peak_number, where starting_values and bounds are in the format that can be passed to mm2_Voigt
    bounds: bounds that work for curvefit, where lower bounds need to be strictly smaller than upper bounds
    bounds_gop: bounds for global optimization, where upper=lower bound for 'fake' parameters speed up the convergence
    NOTE: e,f,g are parameters describing background
    NOTE: h,i,j are parameters describing the amorphous peak
    """
    material_dict={'polypropylene':
                   {'a':[10.06,11.9755312,13.16014013,15.1,15.48067536,17,17.55,19.85],
                    'b':[60,30,30,30,30,5,5,3],
                    'c':[.1,.2,.15,.45,.45,.4,.4,.4],
                    'd':[.5,.5,.5,.5,.5,.5,.5,.5],
                    'e':[1,1,1,1,1,1,1,1],
                    'f':[20,20,20,20,20,20,20,20],  
                    'g':[10,10,10,10,10,10,10,10],
                    'h':[200.,200,200,200,200,200,200,200],
                    'i':[9.,9,9,9,9,9,9,9],
                    'j':[10.,10,10,10,10,10,10,10]},
                   'polypropylene_beta':
                   {'a':[10.02,11.25,11.9048,13.1014013,15.0,15.49,17,17.55,19.85],#'a':[10.02,11.838,11.9748,13.1014013,15.0,15.49],
                    'b':[60,20,30,30,30,30,5,5,3],
                    'c':[.2,.1,.3,.4,.6,.3,.4,.4,.4],
                    'd':[.5,.5,.5,.5,.5,.5,.5,.5,.5],
                    'e':[1,1,1,1,1,1,1,1,1],
                    'f':[20,20,20,20,20,20,20,20,20],  
                    'g':[10,10,10,10,10,10,10,10,10],
                    'h':[200.,200,200,200,200,200,200,200,200],
                    'i':[9.,9,9,9,9,9,9,9,9],
                    'j':[10.,10,10,10,10,10,10,10,10]},
    }
    
    if material == '?':
        print('available materials: %s'%list(material_dict.keys()))
    else: 
        assert material in list(material_dict.keys()), 'ERROR: %s not in list of known materials: %s'%(material,list(material_dict.keys())) 
        if material == 'polypropylene_beta': # need tighter bounds on peak positions for split peak
            a=material_dict[material]['a'];a1=np.array(a)*.98;a1=a1.tolist();a2=np.array(a)*1.005;a2=a2.tolist()
        else:
            a=material_dict[material]['a'];a1=np.array(a)*.98;a1=a1.tolist();a2=np.array(a)*1.02;a2=a2.tolist()
        b=np.array(material_dict[material]['b'])*amplitude_scale;b=b.tolist();b1=np.zeros(len(b)).tolist();b2=np.ones(len(b))*1E4;b2=b2.tolist()
        c=material_dict[material]['c'];c1=np.array(c)*.5;c1=c1.tolist();c2=np.array(c)*2;c2=c2.tolist()
        d=material_dict[material]['d'];d1=np.zeros(len(d)).tolist();d2=np.ones(len(d)).tolist()
        # parameters e - j: we're only using the first element, the rest is fake for convenience
        #e=material_dict[material]['e'];e1=np.ones(len(e))*(-1);e1=e1.tolist();e2=np.ones(len(e))*100;e2=e2.tolist();e1[1:]=e[0]+1E-4;e2[1:]=e[0]-1E-4
        e=material_dict[material]['e'];e1=np.ones(len(e))*(0);e2=np.ones(len(e))*100;e1[1:]=e[0]-1E-6;e2[1:]=e[0]+1E-6;e1=e1.tolist();e2=e2.tolist()
        f=material_dict[material]['f'];f1=np.ones(len(f))*(0);f2=np.ones(len(f))*100;f1[1:]=f[0]-1E-6;f2[1:]=f[0]+1E-6;f1=f1.tolist();f2=f2.tolist()
        g=material_dict[material]['g'];g1=np.ones(len(g))*.1;g2=100*np.ones(len(g));g1[1:]=g[0]-1E-6;g2[1:]=g[0]+1E-6;g1=g1.tolist();g2=g2.tolist()
        h=material_dict[material]['h'];h1=np.ones(len(h))*(0);h2=np.ones(len(h))*1000;h1[1:]=h[0]-1E-6;h2[1:]=h[0]+1E-6;h1=h1.tolist();h2=h2.tolist()
        i=material_dict[material]['i'];i1=np.ones(len(i))*(3);i2=np.ones(len(i))*15;i1[1:]=i[0]-1E-6;i2[1:]=i[0]+1E-6;i1=i1.tolist();i2=i2.tolist()
        j=material_dict[material]['j'];j1=np.ones(len(j))*(7);j2=np.ones(len(j))*15;j1[1:]=j[0]-1E-6;j2[1:]=j[0]+1E-6;j1=j1.tolist();j2=j2.tolist()

        e=material_dict[material]['e'];e1gop=np.ones(len(e))*(0);e2gop=np.ones(len(e))*100;e1gop[1:]=e[0];e2gop[1:]=e[0];e1gop=e1gop.tolist();e2gop=e2gop.tolist()
        f=material_dict[material]['f'];f1gop=np.ones(len(f))*(0);f2gop=np.ones(len(f))*100;f1gop[1:]=f[0];f2gop[1:]=f[0];f1gop=f1gop.tolist();f2gop=f2gop.tolist()
        g=material_dict[material]['g'];g1gop=np.ones(len(g))*.1;g2gop=100*np.ones(len(g));g1gop[1:]=g[0];g2gop[1:]=g[0];g1gop=g1gop.tolist();g2gop=g2gop.tolist()
        h=material_dict[material]['h'];h1gop=np.ones(len(h))*(0);h2gop=np.ones(len(h))*1000;h1gop[1:]=h[0];h2gop[1:]=h[0];h1gop=h1gop.tolist();h2gop=h2gop.tolist()
        i=material_dict[material]['i'];i1gop=np.ones(len(i))*(3);i2gop=np.ones(len(i))*15;i1gop[1:]=i[0];i2gop[1:]=i[0];i1gop=i1gop.tolist();i2gop=i2gop.tolist()
        j=material_dict[material]['j'];j1gop=np.ones(len(j))*(7);j2gop=np.ones(len(j))*15;j1gop[1:]=j[0];j2gop[1:]=j[0];j1gop=j1gop.tolist();j2gop=j2gop.tolist()
        
        C=[];C+=a;C+=b;C+=c;C+=d;C+=e;C+=f;C+=g;C+=h;C+=i;C+=j
        B1=[];B1+=a1;B1+=b1;B1+=c1;B1+=d1;B1+=e1;B1+=f1;B1+=g1;B1+=h1;B1+=i1;B1+=j1
        B2=[];B2+=a2;B2+=b2;B2+=c2;B2+=d2;B2+=e2;B2+=f2;B2+=g2;B2+=h2;B2+=i2;B2+=j2
        bounds=(B1,B2)

        B1gop=[];B1gop+=a1;B1gop+=b1;B1gop+=c1;B1gop+=d1;B1gop+=e1gop;B1gop+=f1gop;B1gop+=g1gop;B1gop+=h1gop;B1gop+=i1gop;B1gop+=j1gop
        B2gop=[];B2gop+=a2;B2gop+=b2;B2gop+=c2;B2gop+=d2;B2gop+=e2gop;B2gop+=f2gop;B2gop+=g2gop;B2gop+=h2gop;B2gop+=i2gop;B2gop+=j2gop
        bounds_gop=(B1gop,B2gop)

        sb1 = np.array(split_array(10,bounds[0]))
        sb2 = np.array(split_array(10,bounds[1]))

        sb1_gop = np.array(split_array(10,bounds_gop[0]))
        sb2_gop = np.array(split_array(10,bounds_gop[1]))
        # sb2[3] = np.ones(len(sb2[3]))*2
        # sb1[3] = -1*sb2[3]
        bounds_=(sb1.flatten().tolist(),sb2.flatten().tolist()) 
        bounds_gop_=(sb1_gop.flatten().tolist(),sb2_gop.flatten().tolist()) 
        pn=int(len(a)) #number of peaks
        
        return C, bounds_, bounds_gop_, pn


def update_background_bounds(starting_values,bounds,bkg_params,pn,perc_low=.1,perc_high=.05):
    """
    function to enforce known limits for constant offset and diffuse scattering
    starting_values, bounds: starting values and bounds to be lmited to kown diffuse scattering contributions (note: only tightening upper bounds -> diffuse scattering can go down during crystallization, but not up)
    bkg_params,bkg_bounds: diffuse scattering background parameters and bounds, can be from mm2_Voigt or separate background fit
    """
    assert len(starting_values) == len(bounds[0]), 'ERROR: need bounds=(upper,lower) with len(upper)=len(lower)=len(params)!'
    
    for i in range(4,7): # this is the diffuse scattering part
        if len(bkg_params) == 10*pn: # -> parameters from mm2_Voigt
            pnn=pn
        elif len(bkg_params) == 6: # -> parameters from separate background fit
            pnn=1
        bounds[0][pn*i]=max([(1-perc_low)*bkg_params[pn*i],0]) # make sure we don't drop to unphysical bounds, here that would be params <0
        starting_values[pn*i] = bkg_params[pnn*i]
        bounds[1][pn*i]=(1+perc_high)*bkg_params[pnn*i]
    return starting_values,bounds


def shake_starting_values(starting_values,pn,perc=.10):
    svl = deepcopy(starting_values)
    svl[pn:2*pn]+= svl[pn:2*pn]*perc*random.random()*np.sign(random.randint(-100,100))
    for w in range(4,10):
      svl[pn*w] += svl[pn*w]*perc*random.random()*np.sign(random.randint(-100,100))
    return svl



#################### try to import these functions... ##############################
def m2_Voigt(x,a,b,c,d,e,f,g,h,i,j):
    y=np.zeros(len(x))
    for r in range(len(a)):
        # if i == 0:
        #     y+=pseudo_Voigt(x,a[i],b[i],c[i],d[i],e[i],f[i])
        # else:
        y+=pseudo_Voigt(x,a[r],b[r],c[r],d[r],e=0,f=0)
    y+=e[0]+f[0]*np.exp(-x/g[0])+((h[0]/(i[0]/2))/np.pi)/(1+((x-j[0])/(i[0]/2))**2)
    return y

def mm2_Voigt(x,*C):
    s=int(len(C)/10) # this is the number of peaks
    a=C[0:s];b=C[s:2*s];c=C[2*s:3*s];d=C[3*s:4*s];e=C[4*s:5*s];f=C[5*s:6*s];g=C[6*s:7*s];h=C[7*s:8*s];i=C[8*s:9*s];j=C[9*s:10*s]
    return m2_Voigt(x,a,b,c,d,e,f,g,h,i,j)

def amorphous_peak(x,a,b,c,d,e,f):
    return a+b*np.exp(-x/c)+((d/(e/2))/np.pi)/(1+((x-f)/(e/2))**2)

# Note: functions below use global variables and need to be defined here
# def sumOfSquaredError2(parameterTuple):
#     global q, ydat
#     warnings.filterwarnings("ignore") # do not print warnings by genetic algorithm
#     val =mm2_Voigt(q, *parameterTuple)
#     return np.sum((ydat - val) ** 2.0)

# def sumOfSquaredError_amorphous(parameterTuple):
#     warnings.filterwarnings("ignore") # do not print warnings by genetic algorithm
#     val =amorphous_peak(q, *parameterTuple)
#     return np.sum((ydat - val) ** 2.0)

# def generate_Initial_Parameters_amorphous(method = 'dual_annealing',workers=1,x0=None,polish=True,tol=.01):
#     if method == 'differential_evolution':
#         result = differential_evolution(sumOfSquaredError_amorphous, Bounds(bounds_amo_[0],bounds_amo_[1]), seed=3,vectorized=False,workers=workers,tol=tol,x0=x0,strategy='best1bin',polish=polish)
#     elif method == 'dual_annealing':
#         result = dual_annealing(sumOfSquaredError_amorphous, Bounds(bounds_amo_[0],bounds_amo_[1]), seed=3, x0=x0)
#     elif method == 'shgo':
#         print('Warning: global optimization method "shgo" might be slow...')
#         result = shgo(sumOfSquaredError_amorphous, Bounds(bounds_amo_[0],bounds_amo_[1]), workers=workers)
#     elif method == 'direct':
#         print('Warning: global optimization method "direct" might be slow...')
#         result = direct(sumOfSquaredError_amorphous, Bounds(bounds_amo_[0],bounds_amo_[1]))
#     else:
#         raise Exception('method %s is unknown...method should be one of "differential_evolution", "dual_annealing", "shgo" or "direct".'%method)
#     return result.x

def generate_Initial_Parameters(bounds_ip,method = 'dual_annealing',workers=1,x0=None,polish=True,tol=.01):
    if method == 'differential_evolution':
        result = differential_evolution(sumOfSquaredError2, Bounds(bounds_ip[0],bounds_ip[1]), seed=3,vectorized=False,workers=workers,tol=tol,x0=x0,strategy='best1bin',polish=polish)
    elif method == 'dual_annealing':
        result = dual_annealing(sumOfSquaredError2, Bounds(bounds_ip[0],bounds_ip[1]), seed=3, x0=x0)
    elif method == 'shgo':
        print('Warning: global optimization method "shgo" might be slow...')
        result = shgo(sumOfSquaredError2, Bounds(bounds_ip[0],bounds_ip[1]), workers=workers)
    elif method == 'direct':
        print('Warning: global optimization method "direct" might be slow...')
        result = direct(sumOfSquaredError2, Bounds(bounds_ip[0],bounds_ip[1]))
    else:
        raise Exception('method %s is unknown...method should be one of "differential_evolution", "dual_annealing", "shgo" or "direct".'%method)
    return result.x


def plot_patternfit_result(peak_fit_dict,frame_nr=-3,ylims=[.5,None],plot_non_crystalline_peak_params=True, plot_more_cryst_onset=True, save_figures=False, figure_dir=None, verbose=False):
    import heapq
    display(clear=True,wait=True)

    try:
        title_str = peak_fit_dict['meta_data']['title string']
    except:
        title_str='scan_id: %s    uid: %s'%(peak_fit_dict['meta_data']['pil800k_scan_id'],peak_fit_dict['meta_data']['pil800k_uid'][:8])
    fig_dict={} # dictionary to return filenames to make a pdf report
    if save_figures and figure_dir is None:
        figure_dir=os.getcwd()
        if verbose:
            print('No directory provided to save figures -> using current working directory %s!'%figure_dir)
    
    fr_list_ = list(peak_fit_dict['fits'].keys())
    fr_list=[]
    if type(frame_nr) == list: # list of fits
        for f in frame_nr:
            if f in fr_list_:
                fr_list.append(f)
    elif type(frame_nr) == int and frame_nr>=0: # single fit 
        if frame_nr in fr_list_:
            fr_list=[frame_nr]
    elif type(frame_nr) == int and frame_nr<0: #range of recent fits
        fr_list=fr_list_[frame_nr:]

    cols=3
    rows=int(np.ceil(len(fr_list)/cols))
    if len(list(peak_fit_dict['non-crystalline fits'].keys())) >0: # also have the fit of the non-crystalline peak!
        rows=2*rows;non_crystalline_fits=True
    else: non_crystalline_fits =False
    
    fig,ax = plt.subplots(rows,cols,figsize=(16,4.5*rows));pc=1
    plt.suptitle(title_str,y=1.02)
    x_waxs=[];x_waxs_err=[];r2=[];offset = [];A_exp=[];q_exp=[]
    for ff,f in enumerate(fr_list):
        plt.subplot(rows,cols,pc)
        if non_crystalline_fits and np.mod(pc,cols) == 0:
            pc=pc+cols
        pc+=1
        x_waxs_=(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['x_waxs'])
        x_waxs_err_=(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['x_waxs_err'])
        r2_=(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['R2'])
        plt.title('frame #%s  model: %s'%(f,peak_fit_dict['fits'][f]['material']))
        plt.loglog(peak_fit_dict['fits'][f]['data']['q'],peak_fit_dict['fits'][f]['data']['ydat'],'k.',markersize=.5)
        plt.loglog(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['all']['q'],peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['all']['yfit'],'r-',label='X$_{waxs}$: %s\nR$^2$: %s'%(np.round(x_waxs_,3),np.round(r2_,4)))
        plt.loglog(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['diffuse bkg']['q'],peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['diffuse bkg']['diffuse_bkg'],'k--')
        plt.loglog(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['amorphous peak']['q'],peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['amorphous peak']['amo_peak'],'g--')
        plt.loglog(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['crystalline peaks']['q'],peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['fits']['crystalline peaks']['cryst_peaks'],'r--',linewidth=1)
        plt.ylabel('WAXS I(Q) [arb.u]');plt.xlabel('Q [nm$^{-1}$]');plt.grid(True,which='both')
        plt.ylim(ylims);plt.legend(loc='best')
    if non_crystalline_fits:
        pc=cols+1
        for ff,f in enumerate(fr_list):
            plt.subplot(rows,cols,pc)
            if np.mod(pc,cols) == 0:
                pc=pc+cols
            pc+=1
            plt.title('frame #%s  model: %s'%(f,peak_fit_dict['non-crystalline fits'][f]['material']))
            plt.loglog(peak_fit_dict['non-crystalline fits'][f]['data']['q'],peak_fit_dict['non-crystalline fits'][f]['data']['ydat'],'k.',markersize=.5)
            plt.loglog(peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['all']['q'],peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['all']['yfit'],'r-',label='X$_{waxs}$: %s\nR$^2$: %s'%(0,np.round(peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['params']['R2'],4)))
            plt.loglog(peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['diffuse bkg']['q'],peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['diffuse bkg']['diffuse_bkg'],'k--')
            plt.loglog(peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['amorphous peak']['q'],peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['fits']['amorphous peak']['amo_peak'],'g--')
            plt.ylabel('WAXS I(Q) [arb.u]');plt.xlabel('Q [nm$^{-1}$]');plt.grid(True,which='both')
            plt.ylim(ylims);plt.legend(loc='best')
    plt.tight_layout()
    if save_figures:
        fn = figure_dir+'/pattern_fits.png'        
        plt.savefig(fn,bbox_inches = "tight");fig_dict['pattern_fits']=fn
        if verbose:
            print('saved pattern fits as %s.'%fn)
    display(plt.gcf())
    plt.close()

    x_waxs=[];x_waxs_err=[];r2=[];offset = [];A_exp=[];q_exp=[];amo_area = [];amo_width=[];amo_q=[];peak_A = [];r2_non_cryst=[]
    for f in sorted(fr_list_):
        x_waxs.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['x_waxs'])
        x_waxs_err.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['x_waxs_err'])
        r2.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['R2'])
        offset.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['e'][0])
        A_exp.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['f'][0])
        q_exp.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['g'][0])
        amo_area.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['h'][0])
        amo_width.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['i'][0])
        amo_q.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['j'][0])
        peak_A.append(peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['params']['b'])
        if non_crystalline_fits:
            r2_non_cryst.append(peak_fit_dict['non-crystalline fits'][f]['fit_params']['pattern_fit']['params']['R2'])

    x_waxs=np.array(x_waxs); x_waxs_err=np.array(x_waxs_err)
    fig,ax = plt.subplots(1,2,figsize=(10,4))
    plt.subplot(1,2,1)
    plt.title('degree of crystallinity')
    plt.plot(sorted(fr_list_),x_waxs)
    plt.fill_between(sorted(fr_list_),x_waxs-x_waxs_err,x_waxs+x_waxs_err,color='C0',alpha=.2)
    plt.ylabel('X$_{waxs}$',color='C0');plt.xlabel('frame no.')
    ax=plt.gca()
    ax2=ax.twinx()
    ax2.plot(sorted(fr_list_),r2,'C1')
    ax2.set_ylabel('R$^2$',color='C1');plt.grid(True,which='both')

    plt.subplot(1,2,2) 
    plt.title('computing times')
    for ff,f in enumerate(sorted(list(peak_fit_dict['fits'].keys()))):
        lab1=None;lab2=None
        if ff == 0:
            lab1='fit';lab2='gop'
        plt.semilogy(f,peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['times']['fit time'],'ko',label=lab1)
        plt.semilogy(f,peak_fit_dict['fits'][f]['fit_params']['pattern_fit']['times']['gop time'],'r+',label=lab2)
    plt.ylabel('computation time [s]');plt.legend(loc='best');plt.grid(True,which='both');plt.xlabel('frame no.')
    plt.tight_layout()
    if save_figures:
        fn = figure_dir+'/crystallinity_computing_time.png'        
        plt.savefig(fn,bbox_inches = "tight");fig_dict['crystallinity_computing_time']=fn
        if verbose:
            print('saved degree of crytallinity and computing times as %s.'%fn)
    display(plt.gcf())
    plt.close()

    fig,ax = plt.subplots(figsize=(8,2))
    plt.title('Degree of Crystallinity')
    f_list = np.array(sorted(fr_list_),dtype=int)
    fr_step_interp = max([1,min(f_list[1:]-f_list[0:-1])])
    fr_interp = np.linspace(min(f_list),max(f_list),1+max(f_list)-min(f_list),dtype=int)
    x_waxs_interp = np.interp(fr_interp,f_list,x_waxs)
    
    mat = np.zeros((1,len(x_waxs_interp)))
    mat[0,:]=x_waxs_interp
    plt.imshow(mat,aspect=20,cmap='jet',extent=(min(fr_interp),max(fr_interp),0,1),interpolation='bilinear')
    plt.xlabel('frame no.');plt.gca().get_yaxis().set_visible(False)
    plt.colorbar(shrink=.4,aspect=2,label='X$_{waxs}$')
    plt.tight_layout()
    if save_figures:
        fn = figure_dir+'/x_waxs_map.png'        
        plt.savefig(fn,bbox_inches = "tight");fig_dict['x_waxs_map']=fn
        if verbose:
            print('saved x_waxs map as %s.'%fn)
    display(plt.gcf())
    plt.close()

    if plot_non_crystalline_peak_params:
        #### diffuse scattering and amorphous peak
        fig,ax = plt.subplots(1,2,figsize=(12,4))
        plt.subplot(1,2,1)
        plt.title('diffuse scattering')
        plt.plot(sorted(fr_list_),offset)
        plt.ylabel('offset',color='C0');plt.xlabel('frame no.')
        ax=plt.gca()
        ax2=ax.twinx()
        ax2.plot(sorted(fr_list_),A_exp,'C1')
        ax2.set_ylabel('A$_{exp}$',color='C1');plt.xlabel('frame no.');plt.grid(True,which='both')
        ax3=ax.twinx();ax3.spines["right"].set_position(("axes", 1.15))
        ax3.plot(sorted(fr_list_),q_exp,color='C2')
        ax3.set_ylabel('q$_{exp}$',color='C2')
        
        plt.subplot(1,2,2)
        plt.title('amorphous peak')
        plt.plot(sorted(fr_list_),amo_area)
        plt.ylabel('peak Area',color='C0');plt.xlabel('frame no.')
        ax=plt.gca()
        ax2=ax.twinx()
        ax2.plot(sorted(fr_list_),amo_width,'C1')
        ax2.set_ylabel('peak width',color='C1');plt.xlabel('frame no.');plt.grid(True,which='both')
        ax3=ax.twinx();ax3.spines["right"].set_position(("axes", 1.15))
        ax3.plot(sorted(fr_list_),amo_q,color='C2')
        ax3.set_ylabel('q$_{AM}$',color='C2')
        plt.tight_layout()
        if save_figures:
            fn = figure_dir+'/non_crystalline_params.png'        
            plt.savefig(fn,bbox_inches = "tight");fig_dict['non_crystalline_params']=fn
            if verbose:
                print('saved plot of non-crystalline fit paramters as %s.'%fn)
        display(plt.gcf())
        plt.close()

    if plot_more_cryst_onset:
        fig,ax = plt.subplots(1,2,figsize=(12,4))
        first_peak_A=[]
        plt.subplot(1,2,1)
        plt.title('crystalline peaks')
        for ff,f in enumerate(sorted(fr_list_)):
            first_peak_A.append(peak_A[ff][0])
            for p in range(len(peak_A[0])):
                plt.semilogy(f,peak_A[ff][p],'.',color='C%s'%p)
        plt.ylabel('A$_i$ crystalline peaks');plt.xlabel('frame no.');plt.grid(True,which='both')
    
        plt.subplot(1,2,2)
        if non_crystalline_fits:        
            plt.title('non-crystalline peak fit')
            plt.plot(sorted(fr_list_),r2_non_cryst,'r-')
            plt.plot(sorted(fr_list_),np.array(first_peak_A)/np.mean(heapq.nlargest(10,first_peak_A)),'k--',label='area of 1$^{st}$ cryst. peak')
            plt.ylabel('R$^2$ non-crystalline fits');plt.xlabel('frame no.');plt.grid(True,which='both');plt.legend(loc='best')
        else:
            plt.axes('off')
        plt.tight_layout()
        if save_figures:
            fn = figure_dir+'/more_crystalline_onset.png'        
            plt.savefig(fn,bbox_inches = "tight");fig_dict['more_crystalline_onset']=fn
            if verbose:
                print('saved plot of additional diagnostics for crystalline onset as %s.'%fn)
        display(plt.gcf())
        plt.close()

    if save_figures:
        return fig_dict