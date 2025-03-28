from pyCHX.chx_packages import *
from IPython.display import clear_output
from pyCHX.chx_generic_functions import append_txtfile
import papermill as pm
import os
import re
from copy import deepcopy
from termcolor import colored

def import_sample_database(collection='data_acquisition_collection'):
    """
    connect to CHX mongoDB 'samples'
    available collections: 'data_acquisition_collection', beamline_pos', 'samples_2'
    returns: pymongo.MongoClient('xf11id-ca').et_database('samples').get_collection(collection)
    """
    import pymongo 
    cli = pymongo.MongoClient('xf11id-ca')    
    print('available databases:')
    print(cli.database_names)
    print('\n available collection in database samples:')
    print(cli.samples.collection_names)
    return cli.get_database('samples').get_collection(collection)
    
def chx_analysis_data( uid , baseDir, alternate_directory=None, verbose=False):            
    
    ''' YG. Octo 6, 2018, Compress a eiger data using papermill
        AF Oct 30, 2020, redefining input, taking username, auto_pipeline and cycle from metadata
        _chx_analysis_data( uid , baseDir, alternate_directory=None)
        Input:
        uid: string, the uique data id OR 
        Note: RE.md must contain - user, cycle and auto_pipeline keywords
        Output:
        save a customized instance of the auto_pipeline to outDir and executed this pipeline through papermill
    '''
    # for ReRun_BatchProcessing, uid is either the uid-string OR a list containing the uid-string + parameters to modify analysis notebook
    if type(uid) !=  str:
        param_dict = do_analysis_setup(uid,baseDir,verbose=False)
        uid = param_dict['uid']
    elif type(uid) == str:
        param_dict=dict();param_dict['uid']=uid
    md_dict=get_meta_data(uid)
    param_dict['username']=md_dict['user'];param_dict['cycle']=md_dict['cycle']
    try:
        param_dict['user_group'] = md_dict['user_group']
    except:
        pass # 'user_group' is a new mandatory metadata starting Feb. 2024. If running an 'old' notebook via papermill, we assume variable 'users' has been hardcoded there and we shouldn't overwrite it e.g. with an empty list.     
    
    #create folders and filenames
    resultsDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/Results' 
    outDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines'
    if alternate_directory!= None:
        outDir = alternate_directory + r+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines/'
        print('running via RADIASOFT environment -> Result directory changed to alternate location: ', outDir )
        resultsDir = alternate_directory +md_dict['cycle']+'/'+md_dict['user']+'/Results'
    template_pipeline = baseDir+md_dict['cycle']+'/AutoRuns/'+md_dict['user']+'/'+md_dict['auto_pipeline']+'.ipynb'
    output_pipeline=outDir+'/'+md_dict['auto_pipeline']+'_%s.ipynb'%uid 
    
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
            md = get_meta_data(uids[i])
            try:
                meas=md['Measurement']
            except:
                meas = ''
            print('[%s] scan_id: %s / uid: %s    %s'%(i,md['scan_id'],uids[i],meas))
        if len(uids)>5:
            print('...')

    
def run_papermill_loop(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,txt_content,baseDir,alternate_directory,verbose=False):
    """
    run_papermill_loop(data_acquisition_collection,direction,list_length,end_of_processing_uid,empty_list_timeout,txt_filename,txt_content,baseDir,alternate_directory,verbose=False)
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
    run_condition = True
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
        N = len(uids)   
        if N>=Nc: # list of uids is not empty
            print('uid list for analysis is NOT empty, found '+str(len(uids))+' uids awaiting analysis.')
            if verbose:
                print('\nNext datasets to be processed by this papermill loop:')
                ct_=np.arange(min(min(len(uids),5),5))
                if direction == 'down':
                    ct_=(ct_+1)*(-1)
                for k in ct_:
                    md = get_meta_data(uids[k])
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
                md_dict=get_meta_data(uid)
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
    
                        chx_analysis_data( uid , baseDir, alternate_directory)  ## MODIFIED FOR RADIASOFT                 
                            # update list of compressed uids:
                        temp2= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_completed']    
                        temp2.append(uid)
                        data_acquisition_collection.update_one({'_id':'general_list'},
                                                        {'$set':{ 'analysis_completed': temp2}})  
                        status='success'

                    except:
                        temp3= data_acquisition_collection.find_one({'_id':'general_list'})['analysis_failed_userX']
                        temp3.append(uids[0])
                        data_acquisition_collection.update_one({'_id':'general_list'},{'$set':{ 'analysis_failed_userX': temp3}})
                        status='failed'
                    #md_dict=get_meta_data(uid)
                    ts = (time.time() - t0)/60 #in unit of min                
                    txt_header = 'fuid, sample, notes, comp_time, comp_status'

                    #ss  = db[uid]['start'] should be able to do without this, if we have md_dict...
                    sample = md_dict['sample']
                    note= md_dict['Measurement']
                    x =   [ uid, sample, note, ts, status  ]  
                    txt_content.append(x)

                    ##remove this uid from  uid in analysis_in_progress
                    temp4 = data_acquisition_collection.find_one({'_id':'general_list'})['analysis_in_progress']
                    tx = [u for u in temp4  if u!=uid ]
                    data_acquisition_collection.update_one( {'_id':'general_list'},
                                                               {'$set':{'analysis_in_progress':  tx }   })     

                    append_txtfile( baseDir + '%s/%s/'%(md_dict['cycle'],md_dict['user']) + txt_filename, data=txt_content, fmt='%s',
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
    files_ = [f for f in os.listdir(path) if re.match('general_', f) and f.split('.')[1]=='npy']
    files=[]
    for f in files_:
        files.append(f.split('general_roi_mask_')[1].split('.')[0])
    if verbose:
        print('available Q-Phi ROI masks: %s'%files)
    return files


def do_analysis_setup(uid,_base_path_,verbose=False):
    tmp = deepcopy(uid);param_dict=dict()
    known_roi_masks = check_roi_masknames(path=_base_path_+'masks/')
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


def check_auto_processing_possible(uid,_base_path_,image_range=None,verbose=False):
    """
    check_auto_processing_possible(uid,_base_path_,image_range=None,verbose=False)
    uid: (full) uid
    range: None -> not checking for range; otherwise: range=[start,stop] with start,stop being integers
    check whether a uid can be processed automatically, either by DataBase analysis of Batch processing
    checks for:
    1. check exit_status: not easily processible IF exit_statis != 'success'
    2. check for mandatory meta_data: user, cycle, auto_pipeline
    3. check whether analysis notebook specified in metadata is in the expected location
    4. eiger detector in detectors?
    5. check whether this is an XPCS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1
    6. if range not None: check whether specified range is within number of collected images
    """
    exit_status=False; md_exist=True; xpcs = True; im_range= True;eiger=False
    
    # 1. check exit_status: not easily processible IF exit_statis != 'success'
    h=db[uid];
    if h.stop['exit_status'] == 'success': exit_status = True
    
    #  2. check for mandatory meta_data: user, cycle, auto_pipeline
    for m in ['user','cycle', 'auto_pipeline']:
        try: 
            h.start[m]
        except: md_exist=False
    
    # 3. check whether analysis notebook specified in metadata is in the expected location
    pp=_base_path_+'%s/AutoRuns/%s/%s'%(h.start['cycle'],h.start['user'],h.start['auto_pipeline']+'.ipynb')
    nb_exists=os.path.isfile(pp)
    
    # 4. eiger detector in detectors?
    for d in h.start['detectors']:
        if re.match('eiger', d):
            eiger=True
    
    #  5. check whether this is an XPCS dataset, red flags: motor involved (-> probably a scan), start['num_intervals'] != 0; start['num_points'] != 1
    try: 
        h.start['motors']
        xpcs = False
    except: pass
    if h.start['num_intervals'] != 0 or h.start['num_points'] != 1:
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
                'md_exist':[md_exist,'some mendatory metadata for "user", "cyle", "auto_pipeline does not exist"'],
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
    
    return sum_status
    