# imports for accessing data from channel archiver
from pyCHX.chx_packages import *
from arvpyf import mgmt, cf
from arvpyf.mgmt import ArchiverConfig
from arvpyf.cf import PVFinder
from arvpyf.ar import ArchiverReader

#setup for CHX archiver
bpl_url = 'http://epics-services-chx.nsls2.bnl.local:18968/mgmt/ui/metrics'
arvconf = ArchiverConfig(bpl_url)
cf_update = '/cf-update/'
pvfinder = PVFinder(cf_update)
ar_url = 'http://epics-services-chx.nsls2.bnl.local:18968'
ar_tz = 'US/Eastern'
config = {'url': ar_url, 'timezone': ar_tz}
arvReader = ArchiverReader(config)

def get_acquisition_start_from_fs(uid,verbose=False):
    """
    determine start of data acquisition for Eigers for a given uid from the fast shutter position:
    assumption: signal to close fast shutter is send at end of data acquisition without delay
    returns: data_start_time [epoch] =  time when the detector actually started taking frames & shutter_close_time [epoch] =  time when the shutter-close signal was sent
    data_start_time = shutter_close_time-(acquire period * number of images)
    [data_start_time, shutter_close_time]
    by LW 04/28/2022
    """
    h=db[uid]
    pv = 'XF:11IDB-ES{Zebra}:SOFT_IN:B0'
    pre=.5 #additional time included in the beginning [s]
    post=.5 #additional time included in the end [s]
    since=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(h.start['time']-pre))
    until=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(h.stop['time']+post))
    df = arvReader.get(pv, since, until)
    #if np.min(df.data.to_numpy()==np.array([0,1,0]))==True:
    if df.data.to_numpy()[-1]==0:
    # got the expected sequence ending with shutter closed
        shutter_close_time=datetime.timestamp(df.time.to_numpy()[-1])
        data_start_time=shutter_close_time-float(h.start['acquire period'])*float(h.start['number of images'])
    else:
        print(df.data.to_numpy())
        data_start_time=np.nan;shutter_close_time=np.nan
        print("couldn't determine data_start_time from shutter position...")
    if verbose:
        print('uid: %s\nstart time of data acquisition: %s  ->   epoch: %ss\nend time of data acquisition: %s   ->  epoch: %ss'
              %(uid,time.strftime('%Y-%m-%d %H:%M:%S:%mS', time.localtime(data_start_time)),data_start_time,time.strftime('%Y-%m-%d %H:%M:%S:%mS',time.localtime(shutter_close_time)),shutter_close_time))
    return [data_start_time,shutter_close_time]


def get_archived_pvs_from_uid(pv_list,uid,pre=0,post=0,verbose=True):
    """
    get_archived_pvs_from_uid(pv_list,uid,pre=0,post=0,verbose=True)
    -> get archived data for a list of PVs, time: between start and stop document of run(uid); use pre and post to extend time before and after
    Note: time of start document is t=0s, "pre" times are negative
    
    pv_list: list of strings that are the PVs for which we want archived data
    uid: uid or short uid of dataset
    pre: time [s] to get data befor time in start document for uid
    post: time [s] to get data past time in stop document for uid
    
    returns: dictionary: {'pv1':{'time':np.array(time [s]),'data':np.array(pv data from archiver)}}
    """
    # datetime has changed from datetime.datetime.timestamp to datetime.timestamp... make sure it works with current and legocy environments
    try:
        datetime.timestamp(datetime.now())
        current=True
    except:
        current=False
    h=db[uid]
    t0=h.start['time'];tmax=h.stop['time']
    since=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0-pre))
    until=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tmax+post))
    if verbose:
        print('getting archived data for PVs %s\nuid: %s\ntime: start of uid - %ss to end of uid +%ss\n%s - %s'%(pv_list,uid,pre,post,since,until))
    pv_dict = {}
    for p in pv_list:
        df = arvReader.get(p, since, until)
        ep_time=[]
        pv_data=[]
        for i in range(np.shape(df.time)[0]):
            if current:
                ep_time.append(datetime.timestamp(df.time[i]))
            else:
                p_time.append(datetime.datetime.timestamp(df.time[i]))
            pv_data.append(df.data[i])
        time_zero=ep_time[0]
        ep_time=np.array(ep_time);pv_data=np.array(pv_data)
        #x=ep_time-t0;y=pv_data
        pv_dict[p]={'time':ep_time-t0,'data':pv_data}
    return pv_dict




print('successfully imported CHX channel archiver and related functions')

