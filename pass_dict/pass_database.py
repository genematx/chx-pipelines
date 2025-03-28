import json
import os
from termcolor import colored
import time    
from IPython.display import clear_output


def pass_functions():
    """
    This function only returns an overview of the functions related to the 'pass database' dictionary. See doc strings of the individual functions for more info.
    dictionary is a json file residing at /nsls2/data/chx/shared/CHX_Software/packages/pass_dict/CHX_PASS_database.json
    Any modification using the functions below will create a time-stamped backup in /nsls2/data/chx/shared/CHX_Software/packages/pass_dict/pass_database_backups/

    get_pass_id(cycle=[], username=None, alias='commissioning, pass_dict='load'): find all pass_ids that match the search criteria

    update_pass_database(pass_dict='load',update_dict=update_dict,autosave=True): updates the database with new entries; can provide a template for 'upadte_dict'

    get_proposal_info(pass_id): get information for a given pass_id, like who's the user, which cycle(s) did this proposal run,...

    remove_pass_dict_entry(pass_dict='load',cycle=[],pass_id=999999): remove a pass_id for a specific cycle or all cycles it appeared in

    Functions not needed for daily interaction:
    save_pass_database(...): low level function to save a given pass_dict as database json file
    load_pass_database(...): low level function to load current database json file and return a pass_dict
    
    01/23/2025 by LW
    """


def load_pass_database(name='CHX_PASS_database',path='/nsls2/data2/chx/shared/CHX_Software/packages/pass_dict/',auto_load=False):
    """
    loads PASS_database stored as json file
    name: name of json file (either with or without file extension)
    path: full path to json file
    auto_load=False -> interactive; ...=True -> non-interactive
    returns: data_base_loaded: dictionary with PASS proposal / user name /alias
    01/23/2025 by LW
    """
    name=name.split('.')[0]
    #path+name+'.json' #just in case file ending had been included in the filename
    if os.path.isfile(path+name+'.json'):

        print(colored('Found existing PASS database %s!'%(path+name+'.json'),'green'))
        if not auto_load:
            inp=input('\nLoad existing database and append? [y,n]:')
        else:
            inp='y'
        if inp in ['y','Y','yes','Yes','YES']:
            print('-> loading database...')
            f = open (path+name+'.json', "r")
            pass_dict = json.loads(f.read()) 
            f.close()
            data_base_loaded = True
        else:
            print(colored('-> creating new database...no worries, existing database will be backed up when saving to file!','yellow'))
            data_base_loaded = False
            pass_dict={}
    else: 
        print(colored('no database found for %s%s -> creating a new one!'%(path,name),'yellow'))
        data_base_loaded = False
        pass_dict={}
    return pass_dict


def update_pass_database(pass_dict,update_dict,autosave=True):
    """
    update current pass_dict with additional PASS information (additional 'experiments')
    pass_dict: current pass_dict (dictionary), e.g. from load_pass_database
    pass_dict='load' -> automatically gets current pass_dict from load_pass_database(...)
    update_dict: dictionary with PASS information
    update_dict = 'template' returns a template for update_dict
    autosave=True: automatically save updated pass_dict as json file (existing json file will be time-stamped and moved to backup)
    returns: pass_dict
    IF update_dict == 'template': returns a template for the update_dict
    01/23/2025 by LW
    """
    if update_dict != 'template':
        if pass_dict == 'load':
            pass_dict = load_pass_database(auto_load=True)
            time.sleep(5) # give people a chance to see the message before -potentially- clear_output() below will remove it
        for k in update_dict:
            if k not in pass_dict.keys():
               pass_dict[k]={}
            for n in update_dict[k]:
                if str(n) in pass_dict[k].keys(): #'str': import from json convertes int to str...
                    al=None
                    try:
                        al=pass_dict[k][n]['alias']
                        al_update_dict[k][n]['alias']
                    except:
                        al=None;al_=None
                    clear_output() # output could become very messy...
                    print(colored('Found existing PASS database entry for cycle: %s  pass_id: %s   user:%s'%(k,str(n),pass_dict[k][str(n)]['username']),'red'))
                    inp=input('\nOverwrite existing entry? [y,n]:')
                    if inp in ['y','Y','yes','Yes','YES']:
                        pass_dict[k][n]=update_dict[k][n]
                        print(colored('Updated existing entry!','green'))
                    else:
                        print(colored('skipping entry','yellow'))
                else:
                    pass_dict[k][str(n)]=update_dict[k][n] 
        if autosave == True:
            save_pass_database(pass_dict,name='CHX_PASS_database',path='/nsls2/data2/chx/shared/CHX_Software/packages/pass_dict/')
        return pass_dict
    elif update_dict == 'template':
        print(colored('template for update_dict ("alias" can be omitted):','green'))
        return {'2525-5':{111110:{'username':'jdoe','alias':'fancy_experiment'},111111:{'username':'kdoe'}}}


def save_pass_database(pass_dict,name='CHX_PASS_database',path='/nsls2/data2/chx/shared/CHX_Software/packages/pass_dict/'):
    """
    function to save pass_dict in json file as database
    IF file already exists: existing file will get a timestamp and moved to a database backup directory
    name: name of database (json file,; works with and without .json)
    path: full path for saving database
    pass_dict: current version of PASS dictionary
    01/23/2025 by LW
    """
    name=name.split('.')[0]
    if os.path.isfile(path+name+'.json'):
        add_string=''
        for i in time.ctime(time.time()).split(' ')[2:]:
            add_string+='_'+i
        print(colored('Database file already exists...saving backup with timestamp in %spass_database_backups/  as %s.json before overwriting existing file!'%(path,name+add_string),color='yellow'))
        if not os.path.isdir(path+'pass_database_backups/'):
            os.mkdir(path+'pass_database_backups/',0o777)
            print('Backup directory does not exist...creating it!')
        os.rename(path+name+'.json', path+'pass_database_backups/'+name+add_string+'.json')
    with open('%s%s.json'%(path,name), "w") as outfile:
        json.dump(pass_dict, outfile)
    print(colored('Saved database as %s%s.json!'%(path,name),color='green'))


def get_pass_id(cycle=[],username='jdoe',alias=None,pass_dict='load'):
    """
    function get pass_id for a list of cycles, a username or an alias
    cycle: list of cycles, e.g. ['2025-1'] or ['2025-1',2024-3]; cycle=[]-> searches in all cycles available in the database
    username='jdoe' or username=None -> ignores user name in search criteria
    alias='commissioning' or alias=None -> ignores alias in search criteria
    pass_dict: current version of PASS dictionary
    pass_dict='load' -> automatically gets current pass_dict from load_pass_database(...)
    returns: pass_id,pass_id_str,return_list
    IF search returns unique result:
        pass_id: integer
        pass_id_str: string pass-xxxxxx
    IF search result is NOT unique:
        pass_id = None
        pass_id_str = None
    return_list: list of dict(s) that match the search criteria, e.g. [{'2525-5':{111110:{'username':'jdoe','alias':'fancy_experiment'}}}]
    01/23/2025 by LW 
    """

    if pass_dict == 'load':
        pass_dict = load_pass_database(auto_load=True)
    if len(cycle)==0: # -> search all cycles
        cycle = pass_dict.keys()
    return_list=[]
    if username is not None or alias is not None:
        for c in cycle:
            for i in pass_dict[c].keys():
                try:
                    al = pass_dict[c][i]['alias']
                except:
                    al=''
                
                if pass_dict[c][i]['username']==username or al==alias:
                    return_list.append({c:{i:pass_dict[c][i]}})
    else:
        for c in cycle:
             return_list.append({c:pass_dict[c]})
    
    pass_id_str=None;pass_id=None
    if len(return_list)==0:
        print(colored('Sorry, did NOT find any entries for cycle=%s, username=%s, alias=%s','yellow'))
    elif len(return_list)==1 and len(list(return_list[0][list(return_list[0].keys())[0]].keys()))==1: # if search returns unique result, return pass_id_str / pass_id for convenience
        pass_id = int(list(return_list[0][list(return_list[0].keys())[0]].keys())[0])
        pass_id_str='pass-%s'%pass_id
    return  pass_id,pass_id_str,return_list


def get_proposal_info(pass_id,pass_dict='load'):
    """
    function to retrieve all available information about a given proposal, specified by pass_id
    pass_id: 111111 or '111111' or 'pass-111111'
    pass_dict: current PASS dictionary
    pass_dict='load' -> load current PASS dictionary via load_pass_database()
    returns: list of dictionaries that contain the pass_id
    01/23/2025 by LW
    """
    pass_id=str(pass_id)
    pass_id=pass_id.split('-')[-1]
    if pass_dict == 'load':
        pass_dict = load_pass_database(auto_load=True)
    return_list=[]
    for k in pass_dict.keys():
        if pass_id in pass_dict[k].keys():
            return_list.append({k:{pass_id:pass_dict[k][pass_id]}})
    return return_list


def remove_pass_dict_entry(pass_dict='load',cycle=[],pass_id=0,autosave=True):
    """
    function to remove pass_id in all or specific cycles
    cycle: list of cycles, e.g. ['2025-1'] or ['2025-1',2024-3]; cycle=[]-> searches in all cycles available in the database
    pass_id: 111111 or '111111' or 'pass-111111'
    pass_dict: current PASS dictionary
    pass_dict='load' -> load current PASS dictionary via load_pass_database()
    autosave=True: automatically save updated pass_dict as json file (existing json file will be time-stamped and moved to backup)
    returns: pass_dict
    01/23/2025 by LW
    """       
    pass_id=str(pass_id)
    pass_id=pass_id.split('-')[-1]

    if pass_dict == 'load':
        pass_dict = load_pass_database(auto_load=True)
    if len(cycle)==0:
        cycle=list(pass_dict.keys())
    found_pass_id=False
    for k in cycle:
        if pass_id in pass_dict[k].keys():
            found_pass_id=True
            print('removing cycle: %s, pass_id: pass-%s :%s'%(k,pass_id,pass_dict[k].pop(pass_id)))
    if not found_pass_id:
        print(colored('Did NOT find any entries for pass-%s in PASS database...'%pass_id,color='yellow'))
    if autosave:
        save_pass_database(pass_dict,name='CHX_PASS_database',path='/nsls2/data2/chx/shared/CHX_Software/packages/pass_dict/')
    return pass_dict