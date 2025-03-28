from pyCHX.chx_packages import *
from IPython.display import clear_output
from pyCHX.chx_generic_functions import append_txtfile
import papermill as pm
import os
import re
from copy import deepcopy
from termcolor import colored
import sys
sys.path.insert(0, "/nsls2/data/chx/shared/CHX_Software/packages/AutoRun_functions/")
from AutoRun_functions import *


def import_sample_database(collection='data_acquisition_collection'):
     """
     connect to CHX mongoDB 'samples'
     available collections: 'data_acquisition_collection', beamline_pos', 'samples_2'
     returns: pymongo.MongoClient('xf11id-ca').et_database('samples').get_collection(collection)
     """
     import pymongo 
     mongo_uri = f"mongodb://{os.environ['MONGO_USER_CHX']}:{os.environ['MONGO_PASSWORD_CHX']}@mongo1.nsls2.bnl.gov,mongo2.nsls2.bnl.gov,mongo3.nsls2.bnl.gov"
     cli = pymongo.MongoClient(mongo_uri)   
     print('available databases:')
     print(cli.database_names)
     print('\n available collection in database samples:')
     print(cli.get_database('chx-samples').collection_names)
     return cli.get_database('chx-samples').get_collection(collection)


def chx_analysis_data( uid , baseDir, mask_path=None, alternate_directory=None, verbose=False, insert_dict=None):            
    
    ''' YG. Octo 6, 2018, Compress a eiger data using papermill
        AF Oct 30, 2020, redefining input, taking username, auto_pipeline and cycle from metadata
        _chx_analysis_data( uid , baseDir, alternate_directory=None, insert_dict=None )
        Input:
        uid: string, the uique data id OR 
        insert_dict: dictionary with parameters to insert into notebook via papermill
        Note: RE.md must contain - user, cycle and auto_pipeline keywords
        Output:
        save a customized instance of the auto_pipeline to outDir and executed this pipeline through papermill
    '''
    # for ReRun_BatchProcessing, uid is either the uid-string OR a list containing the uid-string + parameters to modify analysis notebook
    if not mask_path:
        mask_path_full = '/nsls2/data/chx/shared/masks/' # that's the old legacy mask folder...should disappear at some point. It's currently here for backwards compatibility.
    else: mask_path_full=mask_path+'ROI_masks/'
    if type(uid) !=  str:
        param_dict = do_analysis_setup(uid,mask_path_full,verbose=False)
        uid = param_dict['uid']
    elif type(uid) == str:
        param_dict=dict();param_dict['uid']=uid
    md_dict=get_meta_data(uid)
    param_dict['username']=md_dict['user'];param_dict['cycle']=md_dict['cycle']
    if insert_dict is not None and type(insert_dict) == dict:
        for o in list(insert_dict.keys()):
            param_dict[o]=insert_dict[o]
    try:
        param_dict['user_group'] = md_dict['user_group']
    except:
        pass # 'user_group' is a new mandatory metadata starting Feb. 2024. If running an 'old' notebook via papermill, we assume variable 'users' has been hardcoded there and we shouldn't overwrite it e.g. with an empty list.     
    
    # create filenames
    if not 'proposal' in md_dict.keys(): # before data security... 
        resultsDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/Results' 
        outDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines'
        if alternate_directory!= None:
            outDir = alternate_directory + r+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines/'
            print('running via RADIASOFT environment -> Result directory changed to alternate location: ', outDir )
            resultsDir = alternate_directory +md_dict['cycle']+'/'+md_dict['user']+'/Results'    
        template_pipeline = baseDir+md_dict['cycle']+'/AutoRuns/'+md_dict['user']+'/'+md_dict['auto_pipeline']+'.ipynb'
    elif 'proposal' in md_dict.keys(): # before data security...
        resultsDir = baseDir+md_dict['cycle']+'/'+'pass-%s'%md_dict['proposal']['proposal_id']+'/Results' 
        outDir = baseDir+md_dict['cycle']+'/pass-%s'%md_dict['proposal']['proposal_id']+'/ResPipelines'
        template_pipeline = baseDir+md_dict['cycle']+'/pass-%s'%md_dict['proposal']['proposal_id']+'/AutoRuns'+'/'+md_dict['auto_pipeline']+'.ipynb'
    output_pipeline=outDir+'/'+md_dict['auto_pipeline']+'_%s.ipynb'%uid 
    # check if directories and template file exist
    for dn in [resultsDir, outDir, template_pipeline]:
        if not os.path.exists(dn):
            print(colored('WARNING: Directory / Template not found! Looking for %s'%dn,'yellow'))
    
    if verbose:
        print(param_dict)
       
    # execute notebook through papermill
    pm.execute_notebook(
        template_pipeline, output_pipeline,         
           parameters = param_dict,
            kernel_name='python3', report_mode=True )  

    
def get_masked_analysis_database( start_uid, data_acquisition_collection ):
    '''
    provide the uid for the first run (next uid after start_uid) and get the masked database
    '''
    temp1 = data_acquisition_collection.find_one({'_id':'general_list'})['uid_list']
    for i,  t in enumerate(temp1):
        if t == start_uid:
            print(i,t)
            start_id = i  +1 
    masked = data_acquisition_collection.update_one( 
           {'_id':'general_list'},{'$set':{'analysis_failed_userX':  temp1[:start_id] }   })
 

def list_database_uids(data_acquisition_collection, verbose = False):
    """
    list_database_uids(data_acquisition_collection, verbose = False)
    list uids in database for processing that have not previously been completed or failed to complete
    verbose = True: list details for the next 5 uids in line
    """
    temp1 = data_acquisition_collection.find_one({'_id':'general_list'})['uid_list']
    temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']
    #temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed']
    temp4= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
    s2 = set(temp2)
    #s3 = set(temp3)
    s4 = set(temp4)           
    uids = [x for x in temp1 if x not in s2 and x not in s4] 
    print('uids to be processed that have not been completed or failed: ',uids)
    print('last processed: scan_id: %s / uid: %s\nlast completed: scan_id: %s / uid: %s\nlast failed: scan_id: %s / uid: %s'%(get_meta_data(temp1[-1])['scan_id'],temp1[-1],get_meta_data(temp2[-1])['scan_id'],temp2[-1],get_meta_data(temp4[-1])['scan_id'],temp4[-1]))
    if verbose:
        print('datasets awaiting processing: ')
        for i in range(min(min(len(uids),5),5)):
            md = get_meta_data(uids[i],verbose=False)
            try:
                meas=md['Measurement']
            except:
                meas = ''
            print('[%s] scan_id: %s / uid: %s    %s'%(i,md['scan_id'],uids[i],meas))
        if len(uids)>5:
            print('...')

    
def run_papermill_loop(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,baseDir,alternate_directory,machine=None,track_progress=True,verbose=False):
    """
   run_papermill_loop(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,baseDir,alternate_directory,machine=None,track_progress=True, verbose=False)
    function to run data processing in a loop via papermill
    """
    if direction == 'up' and list_length=='auto':
        Nc=1
    elif direction == 'down' and list_length=='auto':
        Nc=2
    elif type(list_length)==int:
        Nc=list_length
    if direction == 'up':
        next_uid_=0
    elif direction == 'down':
        next_uid_=-1

    time_count=0
    run_condition = True; write_header = True

    if track_progress:
        a=os.getcwd()
        processing_overview_dict_file=a+'/processing_overview_dict.json'
    
    while run_condition:
        clear_output()
        temp1 = data_acquisition_collection.find_one({'_id':'general_list'})['uid_list']
        temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']
        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
        temp4 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_in_progress']
        s2 = set(temp2)
        s3 = set(temp3)
        s4 = set( temp4 )

        ########################################
        ####### Get uids to be processed #######    
        #uids = [x for x in temp1 if x not in s2 and x not in s3] 
        uids = [x for x in temp1 if x not in s2 and x not in s3 and x not in s4 ] 
        ######################################
        # temporary: try to remove non-XPCS data that somehow got added to the database:
        for ui in uids:
            g=db[ui]
            try:
                if not g.start['XPCS_data']:
                    temp3 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                    temp3.append(ui)
                    data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                    print('removed uid: %s -> NOT XPCS data'%ui)
            except: # that md entry is not even there, which should be the case for Pilatus data
                temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                temp3.append(ui)
                data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                print('removed uid: %s -> NOT XPCS data'%ui)
        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
        s3 = set(temp3)
        ########## end of temporary fix
        
        uids = [x for x in temp1 if x not in s2 and x not in s3 and x not in s4 ]               
        N = len(uids)   
        if N>=Nc: # list of uids is not empty
            print('uid list for analysis is NOT empty, found '+str(len(uids))+' uids awaiting analysis.')
            if verbose:
                print('\nNext datasets to be processed by this papermill loop:')
                ct_=np.arange(min(min(len(uids),5),5))
                if direction == 'down':
                    ct_=(ct_+1)*(-1)
                for k in ct_:
                    md = get_meta_data(uids[k],verbose=False)
                    try:
                        meas=md['Measurement']
                    except:
                        meas = ''
                    print('[%s] scan_id: %s / uid: %s    %s'%(k,md['scan_id'],uids[k],meas))
                if len(uids)>5:
                    print('...')
                
            time_count=0
            if end_of_processing_uid != 'none' and uids[next_uid] == end_of_processing_uid: #looking for a stop key, next uid up IS the stop key
                run_condition = False
                print('Stop Key for analysis detected!')

            else:
                uid = uids[next_uid_]
                md_dict=get_meta_data(uid,verbose=False)          
                try:
                    measurement=md_dict['Measurement']
                except:
                    measurement=''
                print('Doing data analysis for scan_id: %s  uid: %s\n%s'%(md_dict['scan_id'],uid,measurement))

                if uid not in s4:
                    t0 = time.time()
                    try:                                        
                        temp4.append( uid )
                        data_acquisition_collection.update_one({'_id':'general_list'},
                                                             {'$set':{ 'analysis_in_progress': temp4}}) 
                        
                        if track_progress: # progress tracking
                            progress_dict_file = get_progress_dict_filename(uid,md['cycle'],md['user'],baseDir)
                            process_id = get_process_id(uid,md['cycle'],md['user'],baseDir,verbose=False) # -> need to pass this to notebook
                            manage_processing_overview(processing_overview_dict_file,process_id,action='start_processing',progress_dict_file=progress_dict_file,machine=machine,verbose=True)
                            insert_dict={'process_id':process_id}
                        else: insert_dict={}
                        
                        #### papermill call ####################
                        chx_analysis_data( uid , baseDir, alternate_directory, insert_dict=insert_dict)  ## MODIFIED FOR RADIASOFT                 
                        #########################################
                        # update list of uids for processing:
                        temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']    
                        temp2.append(uid)
                        data_acquisition_collection.update_one({'_id':'general_list'},
                                                        {'$set':{ 'analysis_completed': temp2}})  
                        status='success'
                        if track_progress: # progress tracking
                                manage_processing_overview(processing_overview_dict_file,process_id,action='finished_processing',machine=None,verbose=True)

                    except:
                        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                        temp3.append(uids[0])
                        data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                        status='failed'
                        if track_progress:
                            manage_processing_overview(processing_overview_dict_file,process_id,action='failed_processing',machine=None,verbose=True)
                        
                    #md_dict=get_meta_data(uid)
                    ts = (time.time() - t0)/60 #in unit of min
                    if write_header:
                        txt_header = 'fuid, sample, notes, comp_time, comp_status';write_header=False
                    else: txt_header = ''
                    
                    #ss  = db[uid]['start'] should be able to do without this, if we have md_dict...
                    sample = md_dict['sample']
                    note= md_dict['Measurement']
                    txt_content =   [ uid, sample, note, ts, status  ]  
                    #txt_content.append(x)

                    ##remove this uid from  uid in analysis_in_progress
                    temp4 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_in_progress']
                    tx = [u for u in temp4  if u!=uid ]
                    data_acquisition_collection.update_one( {'_id':'general_list'},
                                                               {'$set':{'analysis_in_progress':  tx }   })     
                    if 'proposal' not in md_dict.keys():
                        txt_dir = baseDir + '%s/%s/'%(md_dict['cycle'],md_dict['user'])
                    elif 'proposal' in md_dict.keys():
                        txt_dir = baseDir + '%s/%s/AutoRuns/'%(md_dict['cycle'],'pass-'+md_dict['proposal']['proposal_id'])
                    append_txtfile( txt_dir + txt_filename, data=txt_content, fmt='%s',
                            delimiter=',', header= txt_header) 

        else:
            if time_count > empty_list_timeout:
                print('uid list for analysis was empty for > '+str(empty_list_timeout)+'s -> stop looking for new uids')
                run_condition = False 
            else:
                time_count=time_count+5
                print('list of uids for analysis is emtpy...going to look again in 5s.')
                time.sleep(5)  

                
def check_roi_masknames(path,verbose=False):
    files_ = [f for f in os.listdir(path) if re.match('general_', f) and f.split('.')[1]=='json']
    files=[]
    for f in files_:
        files.append(f.split('general_roi_mask_')[1].split('.')[0])
    if verbose:
        print('available Q-Phi ROI masks: %s'%files)
    return files


def do_analysis_setup(uid,mask_path_full,verbose=False):
    tmp = deepcopy(uid);param_dict=dict()
    known_roi_masks = check_roi_masknames(path=mask_path_full)
    rstart = None;rstop=None;q_phi_maskname=None
    if type(tmp)== str:
        param_dict['uid']=tmp
    if type(tmp) == list:
        assert type(tmp[0])==str,'Error: if uid is a list, the first entry needs to be the uid string!'
        param_dict['uid']=tmp[0]
    if type(tmp) ==  list and len(tmp)>1:
        if type(tmp[1]) ==  list: # second element is list with start/stop frames for g_2 calculation
            assert len(tmp[1])==2 and tmp[1][0]<tmp[1][1] and type(tmp[1][0])==int and type(tmp[1][1])==int, '%s -> list with start and stop frames needs to have format [start, stop] with start < stop and start,stop being type int'%tmp
            param_dict['rstart']=tmp[1][0];param_dict['rstop']=tmp[1][1]
        elif type(tmp[1]) ==  str: # second element is string for Q-Phi-mask selection
            assert tmp[1] in known_roi_masks,'ERROR: %s not in list of known ROI masks %s'%(tmp[1],known_roi_masks)
            param_dict['analysis_type_auto']=False
            if 'phi' in tmp[1]:
                 param_dict['qphi_analysis']=True; param_dict['phi_Q_mask']=tmp[1]
            else:
                param_dict['qphi_analysis']=False; param_dict['isotropic_Q_mask']=tmp[1]
            
    if type(tmp) == list and len(tmp) == 3: 
        if type(tmp[2]) ==  list: # third element is list with start/stop frames for g_2 calculation
            assert len(tmp[2])==2 and tmp[2][0]<tmp[2][1] and type(tmp[2][0])==int and type(tmp[2][1])==int, '%s -> list with start and stop frames needs to have format [start, stop] with start < stop and start,stop being type int'%tmp
            param_dict['rstart'] = tmp[2][0]; param_dict['rstop'] = tmp[2][1]
        elif type(tmp[2]) ==  str: # third element is string for Q-Phi-mask selection
            assert tmp[2] in known_roi_masks,'ERROR: %s not in list of known ROI masks %s'%(tmp[2],known_roi_masks)
            param_dict['analysis_type_auto']=False
            if 'phi' in tmp[2]:
                 param_dict['qphi_analysis']=True; param_dict['phi_Q_mask']=tmp[2]
            else:
                param_dict['qphi_analysis']=False; param_dict['isotropic_Q_mask']=tmp[2]
            
    if type(tmp) == list and len(tmp)>3:
        raise Exception('ERROR: %s -> if uid is a list, it can have a maximum of 3 entries: uid, [frame_start,frame_stop], Q-Phi_mask '%tmp)
    if verbose:    
        print('parameters that would be injected by papermill for uid=%s: \n%s'%(tmp,param_dict))
    return param_dict


def check_auto_processing_possible(uid,_base_path_,image_range=None,return_status_dict=False,verbose=False):
    """
    check_auto_processing_possible(uid,_base_path_,image_range=None,verbose=False)
    uid: (full) uid
    range: None -> not checking for range; otherwise: range=[start,stop] with start,stop being integers
    check whether a uid can be processed automatically, either by DataBase analysis or Batch processing
    checks for:
    1. check exit_status: not easily processible IF exit_statis != 'success'
    2. check for mandatory meta_data: user, cycle, auto_pipeline
    3. check whether analysis notebook specified in metadata is in the expected location
    4. eiger detector in detectors?
    5. check whether this is an XPCS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1
    6. if range not None: check whether specified range is within number of collected images
    
    returns:
    if return_status_dict=False (default):
        True if all checks where passed or False if any of the checks failed
    if return_status_dict=True:
        [True/False, status_dict], where status dict contains the results of every individual check
    """
    exit_status=False; md_exist=True; xpcs = True; im_range= True;eiger=False
    
    # 1. check exit_status: not easily processible IF exit_statis != 'success'
    h=db[uid];
    if h.stop['exit_status'] == 'success': exit_status = True
    
    #  2. check for mandatory meta_data: user, cycle, auto_pipechx_analysis_dataline
    for m in ['user','cycle', 'auto_pipeline']:
        try: 
            h.start[m]
        except: md_exist=False
    
    # 3. check whether analysis notebook specified in metadata is in the expected location
    if 'proposal' not in list(h.start.keys()):
        pp=_base_path_+'%s/AutoRuns/%s/%s'%(h.start['cycle'],h.start['user'],h.start['auto_pipeline']+'.ipynb')
    elif 'proposal' in list(h.start.keys()):
        pp=_base_path_+'%s/pass-%s/AutoRuns/%s'%(h.start['cycle'],h.start['proposal']['proposal_id'],h.start['auto_pipeline']+'.ipynb') # note: _base_path_ is a variable here, usually set to either _base_path_ or _base_path_path_
    nb_exists=os.path.isfile(pp)
    
    # 4. eiger detector in detectors?
    try:
        for d in h.start['detectors']:
            if re.match('eiger', d):
                eiger=True
    except:   # sometimes detectors seem to be not defined in the start document...
        for d in list(h.descriptors[1]['object_keys'].keys()):
            if re.match('eiger', d):
                eiger=True
    
    #  5. check whether this is an XPCS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1
    try: 
        h.start['motors']
        xpcs = False
    except: pass
    try:
        if h.start['num_intervals'] != 0 or h.start['num_points'] != 1:
            xpcs=False
    except:
        if h.stop['num_events']['primary'] !=1:
            xpcs=False
    
    # 6. if range not None: check whether specified range is within number of collected images
    if image_range is not None:
        if image_range[0] is not None:
            if image_range[0] <0 or image_range[0]>float(h.start['number of images']):
                im_range=False
        if image_range[1] is not None:
            if image_range[1] <0 or image_range[1]>float(h.start['number of images']):
                im_range=False
    
    sum_status = exit_status*md_exist*xpcs*im_range*nb_exists*eiger
    
    status_dict={'exit_status':[exit_status,'exit status is NOT "success"'],
                'md_exist':[md_exist,'some mandatory metadata for "user", "cyle", "auto_pipeline does not exist"'],
                 'nb_exists':[nb_exists,'analysis notebook %s not found'%pp],
                 'eiger':[eiger,'No Eiger detector found in list of detectors'],
                'xpcs':[xpcs,'scan does not look like an XPCS dataset'],
                'im_range':[im_range,'range %s of frames requested to analyze is not compatible with dataset size %s'%(image_range,h.start['number of images'])]}   
    
    if verbose:
        if sum_status:
            print('summary for auto-processing check for scan_id: %s uid %s:'%(h.start['scan_id'],uid),colored('automated processing should be possible!','green'))
            #print('automated processing should be possible!')
        else:
            print('summary for auto-processing check for scan_id: %s uid %s:'%(h.start['scan_id'],uid),colored('automated processing NOT possible!','red'))
            for k in list(status_dict.keys()):
                if not status_dict[k][0]:
                    print(colored(status_dict[k][1],'red'))
    if return_status_dict:
        return [sum_status,status_dict]
    else:
        return sum_status
    

def check_auto_processing_possible_waxs(uid,_base_path_,return_status_dict=False,verbose=False):
    """
    check_auto_processing_possible_waxs(uid,_base_path_,image_range=None,verbose=False)
    uid: (full) uid
    
    check whether a uid can be processed automatically, either by DataBase analysis or Batch processing
    checks for:
    1. check exit_status: not easily processible IF exit_statis != 'success'
    2. Pilatus800k detector in detectors?
    3. check whether this is a WAXS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1; XPCS_data=True
     
    returns:
    if return_status_dict=False (default):
        True if all checks where passed or False if any of the checks failed
    if return_status_dict=True:
        [True/False, status_dict], where status dict contains the results of every individual check
    """
    exit_status=False; waxs = True ;pilatus800=False
    
    # 1. check exit_status: not easily processible IF exit_statis != 'success'
    h=db[uid];
    if h.stop['exit_status'] == 'success': exit_status = True
    
    # 2. Pilatus800k detector in detectors?
    try:
        for d in h.start['detectors']:
            if re.match('pilatus800', d):
                pilatus800=True
    except:   # sometimes detectors seem to be not defined in the start document...
        try:
            for d in list(h.descriptors[0]['object_keys'].keys()):
                if re.match('pilatus800', d):
                    pilatus800=True
        except:
            pass
        
    #  3. check whether this is a WAXS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1; XPCS_data = True
    try: 
        h.start['motors']
        waxs = False
    except: pass
    try:
        if h.start['num_intervals'] != 0 or h.start['num_points'] != 1:
            waxs=False
    except:
        if h.stop['num_events']['primary'] !=1:
            waxs=False
    try:
        if h.start['XPCS_data']:
            waxs=False
    except:
        pass
    
    
    sum_status = exit_status*waxs*pilatus800
    
    status_dict={'exit_status':[exit_status,'exit status is NOT "success"'],
                 'pilatus800':[pilatus800,'No Pilatus detector found in list of detectors'],
                'waxs':[waxs,'scan does not look like a WAXS dataset'],
                }   
    
    if verbose:
        if sum_status:
            print('summary for auto-processing check for scan_id: %s uid %s:'%(h.start['scan_id'],uid),colored('processing should be possible!','green'))
            #print('automated processing should be possible!')
        else:
            print('summary for processing check for scan_id: %s uid %s:'%(h.start['scan_id'],uid),colored('processing NOT possible!','red'))
            for k in list(status_dict.keys()):
                if not status_dict[k][0]:
                    print(colored(status_dict[k][1],'red'))
    if return_status_dict:
        return [sum_status,status_dict]
    else:
        return sum_status


def update_heartbeat_json(heartbeat_dict,heartbeat_dict_file,verbose=False):
    """
    update json file with heartbeat from papermill notebook
    tries to find existing file @heartbeat_dict_file, if it does not exist, it will create a new one
    heartbeat_dict = {'process_id':%s_user:%s(pipeline,user) ,'info':{'direction':direction,'message':heartbeat_message,'time':heartbeat_time}}
    02/01/2025 by LW
    """
    if os.path.isfile(heartbeat_dict_file): # file exists, laod existing heartbeat_dict
            f = open(heartbeat_dict_file)
            tmp = json.load(f);f.close()
            current_heartbeat_dict=json.loads(tmp);del tmp
            current_heartbeat_dict[heartbeat_dict['process_id']]=heartbeat_dict['info']
            if verbose:
                print('Updated %s with heartbeat from this pipeline'%heartbeat_dict_file)
    else:
        if verbose:
            print('Could not find %s -> creating new json file to collect heartbeats from papermill pipelines'%heartbeat_dict_file)
        current_heartbeat_dict={heartbeat_dict['process_id']:heartbeat_dict['info']}
    # save back to file:
    tmp=json.dumps(current_heartbeat_dict)
    with open(heartbeat_dict_file, "w") as outfile:
        json.dump(tmp, outfile); del tmp


def check_papermill_heartbeat(filename='auto',warning_levels='auto',runtime=None,update_frequency=120,verbose=False):
    """
    check for heartbeats from papermill pipelines to keep track of what these are doing, if some died, etc.
    filename: path/filename for json dict with heartbeat information'; filename='auto' assume current directory (typically ..../AutoRuns/cycle/) and standard filename heartbeat.json
    warning_levels: list with 3 entries, like [10,30,60] -> last heartbeat <=10min ago: green, <=30min ago: yellow, <=60min ago: red, >60min: ignored (assumed dead a long time ago)
    runtime: [min]: how long to check for updates OR None -> look until kernel gets interrupted
    update frequency: [s] how often to check for updates
    02/01/2025 by LW
    """
    
    assert len(warning_levels)==3 or warning_levels == 'auto', 'ERROR: length of warning levels must be 3, e.g. warning_levels = [5,15,60] or warning_levels="auto"'
    if filename=='auto':
        heartbeat_dict_file=os.getcwd()+'/heartbeat.json'
    else:
        heartbeat_dict_file=filename

    if runtime is None:
        stop_time=np.inf
    else:
        stop_time = time.time()+60*runtime
        
    while time.time() < stop_time:
        if verbose:
            print('getting data from : %s'%heartbeat_dict_file)
        f = open(heartbeat_dict_file)
        tmp = json.load(f);f.close()
        current_heartbeat_dict_dict=json.loads(tmp);del tmp
        if warning_levels=='auto':
            warning_levels = [10,30,60]
    
        ignore_count = 0
        print('HEARTBEATS FROM PAPERMILL PROCESSES:')
        for i in current_heartbeat_dict_dict.keys():
            pipeline = i.split('_user:')[0]
            user=i.split('_user:')[1]
            time_stamp=int(np.round((time.time()-current_heartbeat_dict_dict[i]['time'])/60))
    
            if time_stamp <= warning_levels[0]:
                pc='green'
            elif time_stamp > warning_levels[0] and time_stamp <= warning_levels[1]:
                pc='yellow'
            elif time_stamp > warning_levels[1] and time_stamp <= warning_levels[2]:
                pc='red'
                
            
            if time_stamp<=warning_levels[-1]:
                print(colored('%s  run by: %s  direction: %s -> %s  %s min ago'%(pipeline,user,current_heartbeat_dict_dict[i]['direction'],current_heartbeat_dict_dict[i]['message'],time_stamp),pc))
            else:
                ignore_count+=1
        if ignore_count>0:
            print('\n not showing %s processe(s) with most recent heartbeat >%s min ago'%(ignore_count,warning_levels[-1]))
        print('\n')
        for s in tqdm (range(100),desc="waiting for upates from papermill pipelines…",  ascii=False, ncols=200,file=sys.stdout, colour='GREEN'):
            time.sleep(update_frequency/100)
        clear_output()
    print('STOPPED LOOKING FOR UPDATES: runtime of %smin exceeded!'%runtime)


def run_papermill_loop_test(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,baseDir,alternate_directory,session=None,machine=None,track_progress=True,verbose=False,heartbeat=True):
    """
   run_papermill_loop(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,baseDir,alternate_directory,machine=None,track_progress=True, verbose=False)
    function to run data processing in a loop via papermill
    """
    if direction == 'up' and list_length=='auto':
        Nc=1
    elif direction == 'down' and list_length=='auto':
        Nc=2
    elif type(list_length)==int:
        Nc=list_length
    if direction == 'up':
        next_uid_=0
    elif direction == 'down':
        next_uid_=-1

    time_count=0
    run_condition = True; write_header = True

    if track_progress:
        a=os.getcwd()
        processing_overview_dict_file=a+'/processing_overview_dict.json'
    if heartbeat:
        heartbeat_dict_file=os.getcwd()+'/heartbeat.json'
        import getpass
        heartbeat_time = time.time()
        heartbeat_process_id = '%s_user:%s'%(session,getpass.getuser())
        heartbeat_dict={'process_id':heartbeat_process_id,'info':{}}
        
    
    while run_condition:
        clear_output()
        temp1 = data_acquisition_collection.find_one({'_id':'general_list'})['uid_list']
        temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']
        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
        temp4 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_in_progress']
        s2 = set(temp2)
        s3 = set(temp3)
        s4 = set( temp4 )

        ########################################
        ####### Get uids to be processed #######    
        #uids = [x for x in temp1 if x not in s2 and x not in s3] 
        uids = [x for x in temp1 if x not in s2 and x not in s3 and x not in s4 ] 
        ######################################
        # temporary: try to remove non-XPCS data that somehow got added to the database:
        for ui in uids:
            g=db[ui]
            try:
                if not g.start['XPCS_data']:
                    temp3 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                    temp3.append(ui)
                    data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                    print('removed uid: %s -> NOT XPCS data'%ui)
            except: # that md entry is not even there, which should be the case for Pilatus data
                temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                temp3.append(ui)
                data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                print('removed uid: %s -> NOT XPCS data'%ui)
        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
        s3 = set(temp3)
        ########## end of temporary fix
        
        uids = [x for x in temp1 if x not in s2 and x not in s3 and x not in s4 ]               
        N = len(uids)   
        if N>=Nc: # list of uids is not empty
            print('uid list for analysis is NOT empty, found '+str(len(uids))+' uids awaiting analysis.')
            if verbose:
                print('\nNext datasets to be processed by this papermill loop:')
                ct_=np.arange(min(min(len(uids),5),5))
                if direction == 'down':
                    ct_=(ct_+1)*(-1)
                for k in ct_:
                    md = get_meta_data(uids[k],verbose=False)
                    try:
                        meas=md['Measurement']
                    except:
                        meas = ''
                    print('[%s] scan_id: %s / uid: %s    %s'%(k,md['scan_id'],uids[k],meas))
                if len(uids)>5:
                    print('...')
                
            time_count=0
            if end_of_processing_uid != 'none' and uids[next_uid] == end_of_processing_uid: #looking for a stop key, next uid up IS the stop key
                run_condition = False
                print('Stop Key for analysis detected!')

            else:
                uid = uids[next_uid_]
                md_dict=get_meta_data(uid,verbose=False)          
                try:
                    measurement=md_dict['Measurement']
                except:
                    measurement=''
                print('Doing data analysis for scan_id: %s  uid: %s\n%s'%(md_dict['scan_id'],uid,measurement))
                
                if heartbeat:
                    heartbeat_time = time.time()
                    heartbeat_message = 'analysis for scan_id: %s  uid: %s'%(md_dict['scan_id'],uid)
                    heartbeat_dict['info']={'direction':direction,'message':heartbeat_message,'time':heartbeat_time}
                    try:
                        update_heartbeat_json(heartbeat_dict,heartbeat_dict_file,verbose=False)
                        print('process_id: %s  direction: %s  doing:  %s    time: %s'%(heartbeat_process_id,direction,heartbeat_message,heartbeat_time))
                    except:
                        pass
                
                # commented below for testing!
                #time.sleep(30) #'faking' data processing
                if uid not in s4:
                    t0 = time.time()
                    try:                                        
                        temp4.append( uid )
                        data_acquisition_collection.update_one({'_id':'general_list'},
                                                             {'$set':{ 'analysis_in_progress': temp4}}) 
                        
                        if track_progress: # progress tracking
                            progress_dict_file = get_progress_dict_filename(uid,md['cycle'],md['user'],baseDir)
                            process_id = get_process_id(uid,md['cycle'],md['user'],baseDir,verbose=False) # -> need to pass this to notebook
                            manage_processing_overview(processing_overview_dict_file,process_id,action='start_processing',
                                                       progress_dict_file=progress_dict_file,machine=machine,verbose=True)
                            insert_dict={'process_id':process_id}
                        else: insert_dict={}
                        
                        #### papermill call ####################
                        chx_analysis_data( uid , baseDir, alternate_directory, insert_dict=insert_dict)  ## MODIFIED FOR RADIASOFT                 
                        #########################################
                        # update list of uids for processing:
                        temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']    
                        temp2.append(uid)
                        data_acquisition_collection.update_one({'_id':'general_list'},
                                                        {'$set':{ 'analysis_completed': temp2}})  
                        status='success'
                        if track_progress: # progress tracking
                                manage_processing_overview(processing_overview_dict_file,process_id,action='finished_processing',machine=None,verbose=True)

                    except:
                        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                        temp3.append(uids[0])
                        data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                        status='failed'
                        if track_progress:
                            manage_processing_overview(processing_overview_dict_file,process_id,action='failed_processing',machine=None,verbose=True)
                        
                    #md_dict=get_meta_data(uid)
                    ts = (time.time() - t0)/60 #in unit of min
                    if write_header:
                        txt_header = 'fuid, sample, notes, comp_time, comp_status';write_header=False
                    else: txt_header = ''
                    
                    #ss  = db[uid]['start'] should be able to do without this, if we have md_dict...
                    sample = md_dict['sample']
                    note= md_dict['Measurement']
                    txt_content =   [ uid, sample, note, ts, status  ]  
                    #txt_content.append(x)

                    ##remove this uid from  uid in analysis_in_progress
                    temp4 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_in_progress']
                    tx = [u for u in temp4  if u!=uid ]
                    data_acquisition_collection.update_one( {'_id':'general_list'},
                                                               {'$set':{'analysis_in_progress':  tx }   })     
                    if 'proposal' not in md_dict.keys():
                        txt_dir = baseDir + '%s/%s/'%(md_dict['cycle'],md_dict['user'])
                    elif 'proposal' in md_dict.keys():
                        txt_dir = baseDir + '%s/%s/AutoRuns/'%(md_dict['cycle'],'pass-'+md_dict['proposal']['proposal_id'])
                    append_txtfile( txt_dir + txt_filename, data=txt_content, fmt='%s',
                            delimiter=',', header= txt_header) 

        else:
            if time_count > empty_list_timeout:
                print('uid list for analysis was empty for > '+str(empty_list_timeout)+'s -> stop looking for new uids')
                run_condition = False 
            else:
                time_count=time_count+5
                print('list of uids for analysis is emtpy...going to look again in 5s.')

                if heartbeat:
                    if time.time()-heartbeat_time >60: # don't need an update every 5 sec...
                        heartbeat_time = time.time()
                        heartbeat_message = 'waiting for new uid'
                        heartbeat_dict['info']={'direction':direction,'message':heartbeat_message,'time':heartbeat_time}
                        try:
                            update_heartbeat_json(heartbeat_dict,heartbeat_dict_file,verbose=False)
                        except:
                            pass
                        print('process_id: %s  direction: %s  doing:  %s    time: %s'%(heartbeat_process_id,direction,heartbeat_message,heartbeat_time))                
                time.sleep(5)