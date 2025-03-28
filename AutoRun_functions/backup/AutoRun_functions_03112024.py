from pyCHX.chx_packages import *
import json
import os
from collections import OrderedDict

#################################### functions for progress tracking and visualization ##################################
def manage_processing_overview(processing_overview_dict_file,process_id,action,progress_dict_file=None,machine=None,fake_md=None,verbose=False):
    """
    help function to track progress of notebook run via papermill
    creates dictionary file processing_overview_dict.json in .../analysis/cycle/AutoRuns if it doesn't exist
    manage_processing_overview(processing_overview_dict_file,process_id,action,progress_dict_file=None,machine=None,verbose=False)
    progress_dict_file: only neede for 'start_processing'
    processing_overview_dict_file: path/filename to proceccing overview dict, e.g. /analysis/2023/AutRuns/processing_overview_dict.json
    machine: 'machine' from %run /nsls2/data/chx/legacy/analysis/2022_3/lwiegart/development/chx_analysis_setup.ipynb
    action: 'start_processing' -> make entry for process_id in processing_overview_dict['ongoing']
            'finished_processing' -> move entry for process_id from processing_overview_dict['ongoing'] to processing_overview_dict['completed']
            'failed_processing' ->  move entry for process_id from processing_overview_dict['ongoing'] to processing_overview_dict['completed']
                                    & mark all 
    REMOVE FAKE_MD for productions!!!!
    """
    try:
        uid=process_id.split('_')[0]
        if os.path.isfile(processing_overview_dict_file): # file exists, need to get the dictionary to update it
            f = open(processing_overview_dict_file)
            tmp = json.load(f);f.close()
            processing_overview_dict=json.loads(tmp);del tmp
        else:    # file doesn't exist, need to create one, start with empty dictionary
            processing_overview_dict = {'ongoing':{},'completed':{}}
            if verbose:
                print('creating new processing_overview_dict: %s'%processing_overview_dict_file)
        if action == 'start_processing':
            #start, resource, data_id, process_id, analysis_notebook
            md=get_meta_data(uid) # to be used in production
            scan_id = md['scan_id'] 
            analysis_notebook = md['auto_pipeline'] # to be used in production
            #scan_id = fake_md[uid]['scan_id'] #fake for fake test uids, see line above for production
            #analysis_notebook = 'XPCS_SAXS_auto_something_fake' #fake for fake test uids, see line above for production
            processing_overview_dict['ongoing'][process_id]={'start':time.time(),'resource':machine,'data_id':{'uid':uid,'scan_id':scan_id},
                                                             'analysis_notebook':analysis_notebook,'progress_dict_file':progress_dict_file}
            if verbose:
                print('updating processing_overview_dict: process_id = %s -> start'%process_id)
        elif action == 'finished_processing':
            stop_time=time.time()
            processing_overview_dict['completed'][stop_time]=processing_overview_dict['ongoing'][process_id]
            processing_overview_dict['completed'][stop_time]['process_id']=process_id
            processing_overview_dict['completed'][stop_time]['stop']=stop_time
            processing_overview_dict['completed'][stop_time]['elapsed']=stop_time-processing_overview_dict['completed'][stop_time]['start']
            processing_overview_dict['completed'][stop_time]['status']='completed'
            del processing_overview_dict['ongoing'][process_id]
            if verbose:
                print('updating processing_overview_dict: process_id = %s -> completed'%process_id)

        elif action == 'failed_processing':
            stop_time=time.time()
            processing_overview_dict['completed'][stop_time]=processing_overview_dict['ongoing'][process_id]
            processing_overview_dict['completed'][stop_time]['process_id']=process_id
            processing_overview_dict['completed'][stop_time]['stop']=stop_time
            processing_overview_dict['completed'][stop_time]['elapsed']=stop_time-processing_overview_dict['completed'][stop_time]['start']
            processing_overview_dict['completed'][stop_time]['status']='failed'
            del processing_overview_dict['ongoing'][process_id]
            if verbose:
                print('updating processing_overview_dict: process_id = %s -> failed'%process_id)

            # go and mark all pending/running steps in progress dictionary as failed:
            #prog_dict_file = default_dir+'%s/%s/Results/%s/progress_dict_%s.json'%(cycle,username,uid,uid)
            try:
                prog_dict_file = processing_overview_dict['completed'][stop_time]['progress_dict_file']
                f = open(prog_dict_file)
                tmp = json.load(f);f.close()
                progress_dict=json.loads(tmp);del tmp
                process_id_=process_id.split('_')[1]

                for k in list(progress_dict[process_id_].keys()):
                    if progress_dict[process_id_][k]['status'] == 'running':
                        progress_dict[process_id_][k]['status']='failed'
                        progress_dict[process_id_][k]['stop']=time.time()
                        progress_dict[process_id_][k]['elapsed']=progress_dict[process_id_][k]['stop']-progress_dict[process_id_][k]['start']
                    elif  progress_dict[process_id_][k]['status'] == 'pending':
                        progress_dict[process_id_][k]['status']='failed'

                with open(prog_dict_file, "w") as outfile:
                    json.dump(json.dumps(progress_dict), outfile) 
                if verbose:
                    print('successfully updated %s for failed process_id %s'%(prog_dict_file,process_id))
            except:
                if verbose:
                    print('failed to update %s for failed process_id %s'%(prog_dict_file,process_id))

        with open(processing_overview_dict_file, "w") as outfile:
            json.dump(json.dumps(processing_overview_dict), outfile)
    except:
        if verbose:
            print('could not update progress_overview_dict -> skip')
            
def get_progress_dict_filename(uid,cycle,username,default_dir):
    """
    help function to track progress of notebook run via papermill
    create prog_dict_file
    get_progress_dict_filename(uid,cycle,username,default_dir)
    note: cycle and username are likely available as md for the uid, but are passed as separate arguments to this function
    """
    return default_dir+'%s/%s/Results/%s/progress_dict_%s.json'%(cycle,username,uid,uid)

def get_process_id(uid,cycle,username,default_dir,verbose=False):
    """
    help function to track progress of notebook run via papermill
    check what should be the next process_id for data processing of a given uid
    assuming default path and name for progress_dict
    get_process_id(uid,cycle,username,default_dir, verbose=False)
    default_dir = _base_directory_ (/nsls2/data/chx/legacy/analysis/)
    returns: next process_id
    """
    try:
        prog_dict_file = get_progress_dict_filename(uid,cycle,username,default_dir)
        if verbose:
            print('uid: %s\nlooking for existing progress dictionary in %s'%(uid,prog_dict_file))
        if os.path.isfile(prog_dict_file): # file exists, need to get the last process_id
            f = open(prog_dict_file)
            tmp = json.load(f);f.close()
            tmp_progress_dict=json.loads(tmp);del tmp
            next_process_id = uid+'_%s'%(max(np.array(list(tmp_progress_dict.keys()),dtype=int))+1)
        else:
            next_process_id = uid+'_%s'%0
        if verbose:
            print('next process_id for uid %s is %s'%(uid,next_process_id))
        return next_process_id
    except:
        if verbose:
            print('could not get new process_id -> setting process_id to 999')
        return '%s_999'%uid
    
def create_new_prog_dict_run_XPCS_SAXS(prog_dict_file,process_id,settings_dict, verbose=False):
    """
    help function to track progress of notebook run via papermill
    create a new run (process_id) in an existing progress_dict OR create the progress_dict, if it doesn't exist
    if the process_id already exists in the progress_dict: assume analysis notebook is NOT run via papermill and do NOT track progress via dictionary
    create_new_prog_dict_run_XPCS_SAXS(prog_dict_file,process_id)
    prog_dict_file: path/filename to progress dict
    process_id: id of the current data processing run, for instance uid_2 for the second time data for uid is being processed
    settings_dict: pass settings of analysis notebook: {'run_one_time':run_one_time,'run_two_time',run_two_time,xsvs,xsvs} -> will only create progress entries for analysis steps that are being run
    it will create progress entries () for 'Load data and compress';'calculate g2'; 'calculate 2TCF'; 'calculate XSVS'; 'save data and report'
    returns: track_progress = True/False whether or not to track progress via progress dictionary
    """
    try:
        track_progress = True
        process_id_=int(process_id.split('_')[1])
        settings_dict.update({'Load data and compress':True,'save data and report':True})
        prog_dict_entry={process_id_:OrderedDict()}
        for s in ['Load data and compress','run_one_time','run_two_time','xsvs','save data and report']:
            if settings_dict[s]:
                prog_dict_entry[process_id_][s]={'start':None,'stop':None,'elapsed':None,'status':'pending'}

        ## check if pro_dict_file exists: 
        if os.path.isfile(prog_dict_file): # file exists, need to update
            f = open(prog_dict_file)
            tmp = json.load(f);f.close()
            tmp_progress_dict=json.loads(tmp);del tmp
            if str(process_id_) in list(tmp_progress_dict.keys()): #no updated process_id: this is a notebook copy run outside of papermill -> not tracking progress
                track_progress = False
                if verbose:
                    print('Data has been already processed under process_id %s -> not tracking progress...'%process_id)
            else:
                tmp_progress_dict.update(prog_dict_entry)
        else:
            tmp_progress_dict = prog_dict_entry
        tmp=json.dumps(tmp_progress_dict)
        with open(prog_dict_file, "w") as outfile:
            json.dump(tmp, outfile); del tmp
        if verbose and track_progress:
            print('updated %s for process_id %s'%(prog_dict_file,process_id))
        return track_progress
    except:
        if verbose:
            print('could not create progress_dict (entry) for process_id %s -> not tracking progress'%process_id)
        return  False
    
def update_prog_dict_run_XPCS_SAXS(prog_dict_file,process_id,progress_key, progress,start_time=None, stop_time=None, verbose=False):
    """
    help function to track progress of notebook run via papermill
    function updates progress of individual steps in data processing
    update_prog_dict_run_XPCS_SAXS(prog_dict_file,process_id,progress_key, progress,start_time=None, stop_time=None verbose=False)
    prog_dict_file: full path+filename to json dictionary storing the progress
    process_id: id of processing run to be updated
    progress_key: dictionary key like "run_one_time"
    progress: 'start' or 'stop', 'start': sets "start" to start_time (end_time is ignored) & "status" to 'running'; 'stop': sets "end" to stop_time (start_time is ignored) and calculates "elapsed" & "status" to 'complete'
    start_time: start time for data processing related to this process_key
    stop_time: stop time for data processing related to this process_key
    """
    process_id_=int(process_id.split('_')[1])
    try:
        # get dictionary from json file:
        f = open(prog_dict_file)
        tmp = json.load(f);f.close()
        progress_dict=json.loads(tmp);del tmp

        if progress == 'start':
            progress_dict[str(process_id_)][progress_key]['start']=start_time
            progress_dict[str(process_id_)][progress_key]['status']='running'
        elif progress == 'stop':
            progress_dict[str(process_id_)][progress_key]['stop']=stop_time
            progress_dict[str(process_id_)][progress_key]['elapsed']=stop_time-progress_dict[str(process_id_)][progress_key]['start']
            progress_dict[str(process_id_)][progress_key]['status']='complete'

        with open(prog_dict_file, "w") as outfile:
            json.dump(json.dumps(progress_dict), outfile)
        if verbose:
            print('updated %s for process_id %s'%(prog_dict_file,process_id))
            print('progress: %s    progress_key: %s'%(progress,progress_key))
    except:
        if verbose:
            print('could not update progress_dict for process_id %s -> skip!'%process_id)
            
def visualize_processing_overview_dict(processing_overview_dict_file,max_completed=10,max_statistic=20,current_timeout=None,complete_timeout=None,update_time=None,verbose=False):
    """
    help function to track progress of notebook run via papermill
    visualize_processing_overview_dict(processing_overview_dict_file,max_completed=10,max_statistic=20,timeout=None,update_time=None,verbose=False)
    loading data from processing_overview_dict_file & loads more detailed information from progress_dict for individual uids
    max_completed: maximum number of completed process_ids for which to show detailed report
    max_statistic: statistic like runtime fail/completed for the last number of max_statistic process_ids
    current_timeout: None or number; if None: ignored; if number: maximum runtime [min] after which a process_id that still reports 'ongoing' will be ignored
    complete_timeout: None or number; if None: ignored; if number: maximum time [min] up to which completed datasets will be shown
    update_time: None -> single execution of visualization; it not None: refresh time [s], will keep updating for 10k x refresh time
    """
    color_dict = {'running': 'gold',  'complete': 'green',  'pending': 'lightgray',  'failed': 'firebrick'}
    if update_time == None:
        reps=1
    else: reps = 1E4
    for r in range(int(reps)): # loop for continous updates
        
        # reading processing_overview_dict file
        f = open(processing_overview_dict_file)
        tmp = json.load(f);f.close()
        processing_overview_dict=json.loads(tmp);del tmp

        ## process_ids currently being processed
        ol = np.flip(list(processing_overview_dict['ongoing'].keys()))

        ignore_count=0
        for oo,o in enumerate(ol):
            try:
                resource = processing_overview_dict['ongoing'][o]['resource']
                notebook = processing_overview_dict['ongoing'][o]['analysis_notebook']
                process_id = o
                scan_id = processing_overview_dict['ongoing'][process_id]['data_id']['scan_id']
                elaps = time.time()-processing_overview_dict['ongoing'][process_id]['start']
                if current_timeout != None and elaps > timeout*60: # ignore datasets that claim to be still running after >timeout[min]
                    ignore_count+=1
                    if verbose:
                        print('ignoring process_id: %s -> running since > %s minutes'%(o,timeout))
                else:
                    elaps_u='seconds'
                    if elaps >300:
                        elaps=int(np.round(elaps/60))
                        elaps_u='minutes'
                    else:
                        elaps = int(np.round(elaps))
                    sprocess_id=process_id.split('_')[0][:8]+'..._'+process_id.split('_')[1]
                    uid = process_id.split('_')[0]
                    process_id_ = process_id.split('_')[1]

                    # loading progress_dict for individual uid:
                    prog_dict_file = processing_overview_dict['ongoing'][o]['progress_dict_file']
                    f = open(prog_dict_file)
                    tmp = json.load(f);f.close()
                    tmp_progress_dict=json.loads(tmp);del tmp

                    k=list(tmp_progress_dict[process_id_].keys()) # list of tasks that were run
                    task_width = 1/len(k)

                    fig, ax = plt.subplots(figsize=(16,1))
                    if oo == 0:
                        plt.suptitle('CURRENTLY RUNNING DATA PROCECSSING:', fontsize=16,y=1.6)
                    plt.title('process_id: %s  resource: %s   notebook: %s\nrunning since: %s %s'%(sprocess_id,resource,notebook,elaps,elaps_u),horizontalalignment='center',fontsize=12)

                    ax.xaxis.set_visible(False)
                    ylab='uid: %s\nscan_id: %s'%(uid[:8],scan_id)
                    for i in list(color_dict.keys()):
                        d=ax.barh(ylab,task_width,left=0,color=color_dict[i],label=i)
                    ax.set_xlim(0,1)
                    height=0
                    for ll,l in enumerate(k):
                        p = ax.barh(ylab, task_width, label=None, left=height,color=color_dict[tmp_progress_dict[process_id_][l]['status']], edgecolor='k')
                        height += task_width
                        plt.text(.01+task_width*ll,0,l)
                    plt.legend(ncol=4,loc='upper left',bbox_to_anchor=(0,-.02))
                    display(plt.gcf())
                    plt.close()
            except:
                if verbose:
                    print('could not find progress_dict for process_id %s -> skip'%process_id)
        if ignore_count>0:
            print('ignored %s process_ids -> running since > %s minutes'%(ignore_count,timeout))

        ## process_ids previously processed
        cl = np.flip(sorted(list(processing_overview_dict['completed'].keys()))[-max_completed:])
        ignore_count_=0
        for cc,c in enumerate(cl):
            try:
                fin_time=int(np.round((time.time()-processing_overview_dict['completed'][c]['stop'])/60))
                process_id = processing_overview_dict['completed'][c]['process_id']
                if complete_timeout != None and fin_time > complete_timeout: # ignore datasets that claim to be still running after >timeout[min]
                    ignore_count+=1
                    if verbose:
                        print('ignoring process_id: %s -> completed > %s minutes ago'%(process_id,complete_timeout))
                else:
                    resource = processing_overview_dict['completed'][c]['resource']
                    notebook = processing_overview_dict['completed'][c]['analysis_notebook']
                    #process_id = processing_overview_dict['completed'][c]['process_id']
                    scan_id = processing_overview_dict['completed'][c]['data_id']['scan_id']
                    elaps = int(np.round(processing_overview_dict['completed'][c]['elapsed']))
                    elaps_u='seconds'
                    if elaps >300:
                        elaps=int(np.round(elaps/60))
                        elaps_u='minutes'
                    #fin_time=int(np.round((time.time()-processing_overview_dict['completed'][c]['stop'])/60))
                    sprocess_id=process_id.split('_')[0][:8]+'..._'+process_id.split('_')[1]
                    uid = process_id.split('_')[0]
                    process_id_ = process_id.split('_')[1]

                    # loading progress_dict for individual uid:
                    prog_dict_file = processing_overview_dict['completed'][c]['progress_dict_file'] # data_dir0+'%s/progress_dict_%s.json'%(uid,uid)
                    f = open(prog_dict_file)
                    tmp = json.load(f);f.close()
                    tmp_progress_dict=json.loads(tmp);del tmp

                    k=list(tmp_progress_dict[process_id_].keys()) # list of tasks that were run
                    task_width = 1/len(k)


                    fig, ax = plt.subplots(figsize=(16,.5))
                    if cc == 0:
                        plt.suptitle('LAST COMPLETED DATA PROCECSSING:', fontsize=16,y=2.3)
                    plt.title('process_id: %s  resource: %s   notebook: %s\nfinished: %s minutes ago    runtime: %s %s'%(sprocess_id,resource,notebook,fin_time,elaps,elaps_u),horizontalalignment='center',fontsize=12)

                    ax.xaxis.set_visible(False)
                    ylab='uid: %s\nscan_id: %s'%(uid[:8],scan_id)
                    for i in list(color_dict.keys()):
                        d=plt.barh(ylab,task_width,left=0,color=color_dict[i],label=i)
                    plt.xlim(0,1)
                    height=0#;task_width=.2;k=['t1','t2','t3','t4','t5'];ylab='uid'
                    for ll,l in enumerate(k):
                        p = ax.barh(ylab, task_width, label=None, left=height,color=color_dict[tmp_progress_dict[process_id_][l]['status']], edgecolor='k')
                        #p = ax.barh(ylab, task_width, label=None, left=height,color='C%s'%(r+ll), edgecolor='k')
                        height += task_width
                        plt.text(.01+task_width*ll,0,l)
                    plt.legend(ncol=4,loc='upper left',bbox_to_anchor=(0,-.02))
                    display(plt.gcf())
                    plt.close()
            except:
                if verbose:
                    print('could not find progress_dict for process_id %s -> skip'%process_id) 
            
       
        # plot some statistics:
        cl = np.flip(sorted(list(processing_overview_dict['completed'].keys()))[-max_statistic:])
        com_count=0;fail_count=0;runtime=[]
        for c in cl:
            fin_time=int(np.round((time.time()-processing_overview_dict['completed'][c]['stop'])/60))
            process_id = processing_overview_dict['completed'][c]['process_id']
            if complete_timeout != None and fin_time > complete_timeout: # ignore datasets that finished processing >complete_timeout[min] ago
                if verbose:
                    print('ignoring process_id: %s -> completed > %s minutes ago'%(process_id,complete_timeout))
            else:
                if  processing_overview_dict['completed'][c]['status'] == 'completed':
                    com_count+=1;runtime.append(processing_overview_dict['completed'][c]['elapsed'])
                elif processing_overview_dict['completed'][c]['status'] == 'failed':
                    fail_count+=1
            
        fig,ax = plt.subplots(1,2,figsize=(18,4),width_ratios=[1,3])
        plt.subplot(1,2,1)
        plt.title('last %s process_ids'%(fail_count+com_count))
        labels = ['failed','completed']
        if fail_count >0 or com_count>0:
            plt.pie([fail_count,com_count], labels=labels,colors=[color_dict['failed'],color_dict['complete']], autopct='%1.1f%%');

        
        #################### add stacked bar plot with individual run times
        elaps = int(np.round(processing_overview_dict['completed'][c]['elapsed']))
        
        
        
        plt.subplot(1,2,2)
        color_dict_={}; pc=0;t_lab=[];other_lab = 'other'
        for c in cl:
            fin_time=int(np.round((time.time()-processing_overview_dict['completed'][c]['stop'])/60))
            process_id = processing_overview_dict['completed'][c]['process_id']
            if complete_timeout != None and fin_time > complete_timeout: # ignore datasets that finished processing >complete_timeout[min] ago
                if verbose:
                    print('ignoring process_id: %s -> completed > %s minutes ago'%(process_id,complete_timeout))
            else:
                if  processing_overview_dict['completed'][c]['status'] == 'completed':
                    t_lab.append('#%s\n%s'%(processing_overview_dict['completed'][c]['data_id']['scan_id'],processing_overview_dict['completed'][c]['data_id']['uid'][:8]))
                    total_time = processing_overview_dict['completed'][c]['elapsed']
                    prog_dict_file = processing_overview_dict['completed'][c]['progress_dict_file'] # data_dir0+'%s/progress_dict_%s.json'%(uid,uid)
                    f = open(prog_dict_file)
                    tmp = json.load(f);f.close()
                    tmp_progress_dict=json.loads(tmp);del tmp

                    p_id=processing_overview_dict['completed'][c]['process_id'].split('_')[1]

                    bottom = 0
                    for k in list(tmp_progress_dict[p_id].keys()):
                        lab=None
                        if k not in list(color_dict_.keys()):
                            color_dict_[k]=len(list(color_dict_.keys()))
                            lab=k

                        plt.bar(pc, tmp_progress_dict[p_id][k]['elapsed'], .5,color='C%s'%color_dict_[k], label=lab, bottom=bottom)
                        bottom += tmp_progress_dict[p_id][k]['elapsed']
                    # add 'other' time:
                    plt.bar(pc, total_time-bottom, .5,color='C7', label=other_lab, bottom=bottom);other_lab=None
                    pc+=1
        plt.xticks(np.arange(pc),t_lab,rotation=60,fontsize=8);plt.xlim(-1,21)
        plt.ylabel('runtime [s]');plt.grid(True, which='major', axis='y',linestyle='--')
        plt.legend(ncol=3,loc='lower left',bbox_to_anchor=(.01,1.0))
        
        
        ###########################################################################
        # plt.subplot(1,3,3)
        # plt.hist(np.array(runtime)/60,bins=np.array([0,3,7,12,20,60])/20,edgecolor='k',align='mid')  ### remove divider on bins for production!
        # plt.xlabel('runtime [min]');plt.ylabel('number of process_ids');plt.grid(True)
        # plt.title('runtime of last %s successfully completed process_ids'%len(runtime))
        display(plt.gcf())
        plt.close()
        
        
        if update_time != None:
            for i in tqdm(range(update_time), desc="wait for update: ", unit="second"):
                time.sleep(1)  
            display(clear=True,wait =True)

    