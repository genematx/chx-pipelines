from pyCHX.chx_packages import *
from IPython.display import clear_output
from pyCHX.chx_generic_functions import append_txtfile
import papermill as pm

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
    
def _chx_analysis_data( uid , baseDir, alternate_directory=None):            
    
    ''' YG. Octo 6, 2018, Compress a eiger data using papermill
        AF Oct 30, 2020, redefining input, taking username, auto_pipeline and cycle from metadata
        _chx_analysis_data( uid , baseDir, alternate_directory=None)
        Input:
        uid: string, the uique data id 
        Note: RE.md must contain - user, cycle and auto_pipeline keywords
        Output:
        save a customized instance of the auto_pipeline to outDir and executed this pipeline through papermill
    '''
    md_dict=get_meta_data(uid)
    resultsDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/Results' 
    outDir = baseDir+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines'
    if alternate_directory!= None:
        outDir = alternate_directory + r+md_dict['cycle']+'/'+md_dict['user']+'/ResPipelines/'
        print('running via RADIASOFT environment -> Result directory changed to alternate location: ', outDir )
        resultsDir = alternate_directory +md_dict['cycle']+'/'+md_dict['user']+'/Results'
    template_pipeline = baseDir+md_dict['cycle']+'/AutoRuns/'+md_dict['user']+'/'+md_dict['auto_pipeline']+'.ipynb'
    output_pipeline=outDir+'/'+md_dict['auto_pipeline']+'_%s.ipynb'%uid 
    pm.execute_notebook(
        template_pipeline, output_pipeline,         
           parameters = dict( uid = uid, 
                             username      =  md_dict['user'] ,
                             cycle         =  md_dict['cycle'],
                             run_two_time  =   True,
                             run_dose      =   False   ),
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
    
                        _chx_analysis_data( uid , baseDir, alternate_directory)  ## MODIFIED FOR RADIASOFT                 
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

