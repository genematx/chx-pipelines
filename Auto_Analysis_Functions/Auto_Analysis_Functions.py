######################################################################################
########Feb 23, 2019, Lutz Wiegart, lwiegart@bnl.gov, CHX, NSLS-II, BNL###############
########automated fitting, one time correlation function, parameter search############
######################################################################################

import numpy as np
import sys
from scipy import signal
from scipy.optimize import curve_fit
from copy import deepcopy

def printc(text,styles=None,color=None):
    """
    function printc(text,styles=None,color=None) -> prints colored and formatted text (not all formatting options work in all environments)
    example: printc('hello world!',styles=['bold'],color=fail)
    styles: bold','italic','underline
    colors: 'blue','green','cyan','purple','warning' (orange), 'fail (red)
    """
    style_dict={'bold':'\033[1m','italic':'\x1b[3m','underline':'\033[4m'}
    color_dict={'blue':'\033[94m','green':'\033[92m','cyan':'\033[96m','purple':'\033[95m','warning':'\033[93m','fail':'\033[91m'}
    style_str='';color_str=''
    if styles==None and color==None:
        print(text)
    else:
        if styles != None:
            for s in styles:
                try:
                    style_str+=style_dict[s]
                except:
                    print('unrecognized style keyword: %s'%s)
        if color != None:
            try:
                color_str=color_dict[color]
            except: 
                print('unrecognized color keyword: %s'%color)
        print(style_str+color_str+text+'\033[0m')
    


def butterworth_filter(x,y,order,span):
    try:
        # first: remove potential nan values:
        ind = np.isnan(np.array(y))
        ind = [not i for i in ind]
        yn = np.array(y)[ind]
        xf = np.array(x)[ind]
        b, a = signal.butter(order, span)
        zi = signal.lfilter_zi(b, a)
        z, _ = signal.lfilter(b, a, yn, zi=zi*yn[0])
        z2, _ = signal.lfilter(b, a, z, zi=zi*z[0])
        yf = signal.filtfilt(b, a, yn)
        return xf,yf
    except:
        print('failed to apply butterworth filter...potentially data is shorter than min_padlen -> return original data')
        return x,y

def g2_fit_func(x, a, b, c, d):
    return a*np.exp( -2*(b*x)**c) +d    # a -> beta; b -> Gamma; c-> gamma; d-> baseline

# def R_2(ydata,fit_data):
#                     y_ave=np.average(ydata)
#                     SS_tot=np.sum((np.array(ydata)-y_ave)**2)
#                     #print('SS_tot: %s'%SS_tot)
#                     SS_res=np.sum((np.array(ydata)-np.array(fit_data))**2)
#                     #print('SS_res: %s'%SS_res)
#                     return 1-SS_res/SS_tot
def R_2(ydata,fit_data,weights='none'):
    ''' Calculates R squared for a particular fit - by L.W.
    usage R_2(ydata,fit_data,weights='none')
    returns (weighted) R2 
    replaces former R_2 without weight option
    by L.W. Nov. 2021
    '''
    if np.size(weights) == 1 and weights == 'none':
        weights=np.ones(len(ydata))
    y_ave=np.average(ydata,weights=weights)
    SS_tot=np.sum((np.array(ydata)-y_ave)**2*weights)
    SS_res=np.sum(((np.array(ydata)-np.array(fit_data)))**2*weights)
    return 1-SS_res/SS_tot

def check_fit_conditioning(p0,bounds,adjust='boundaries'):
    """
    function to check the initial conditioning of a fit: are the starting values within the boundaries or not?
    if not: adjustust='boundaries' -> adjust boundaries to accomodate starting value
       adjust='start' -> adjust starting values: chose middle of boundaries; adjust='bounds' -> adjust boundaries to satering value 
    returns: [adjusted,p0,bounds]: adjusted=True/False -> indicates whether original p0,bounds were modified; p0/bounds: new starting values/bounds
    """
    adjusted=False
    for ii,i in enumerate(p0):
        if i < bounds[0][ii]:
            adjusted=True
            if adjust=='boundaries':
                bounds[0][ii]=bounds[1][ii]-(bounds[1][ii]*1.00001)
            elif adjust=='start':
                p0[ii]=bounds[0][ii]
        elif i > bounds[1][ii]:
            adjusted=True
            if adjust=='boundaries':
                bounds[1][ii]=bounds[1][ii]+(bounds[1][ii]*1.00001)
            elif adjust=='start':
                p0[ii]=bounds[1][ii]
    for ii,i in enumerate(p0):
        if np.abs(bounds[0][ii]-bounds[1][ii])<1E-6:
            adjusted=True
            bounds[0][ii]=bounds[1][ii]-(bounds[1][ii]*1.0001)
            bounds[1][ii]=bounds[1][ii]+(bounds[1][ii]*1.0001)        
    return adjusted,p0,bounds

# def initial_fit(total_res,extract_dict,phi_analysis,phi,phi_nr,Q_nr,r2_thresh = .8,verbose=False,plotting=False, *argv, **kwargs):
#     """
#     function for initial fit of  dataset
#     total_res -> loaded hdf5 file from XPCS_Single
#     extract_dict -> loaded hdf5 with aged g2s
#     returns: [raw_data,boundatries]
#     """
        
#     if 'MAD_thresh' in kwargs.keys():
#         MAD_thresh= kwargs['MAD_thresh']
#     else:
#         MAD_thresh=1
#     if 'contrast_points' in kwargs.keys():
#         contrast_points=kwargs['contrast_points']
#     else: contrast_points=4
#     if 'base_slope' in kwargs.keys():
#         base_slope=kwargs['base_slope']
#     else: base_slope=.001
#     if 'gisaxs' in kwargs.keys():
#         gisaxs_analysis=kwargs['gisaxs']
#     else: gisaxs_analysis = False
            
    
#     auto_determine_datasets=True # at this point, there is no manual option...
    
#     if not verbose:
#         print('Note: "verbose=False" -> text output is off')
#     if not plotting:
#         print('Note: "plotting=False" -> plots are off')
#     r2_contrast_thresh = -999 # it's programed in, but not sure how to use it: flat contrast region doesn't give a good R2...(same problem with baseline, for which currently no R2 is implemented)
#     # new: ensure that ROI assignment is correct...there was a discrepancy with ordering in total_res and extract_dict for data processed on xf11id-srv2
#     roi_dict={}
#     for ii,i in enumerate(extract_dict['q_dictionary']):
#         roi_dict[ii]=i
#     raw_data={}
#     boundaries={}
#     for q in Q_nr:
#         roi_nr=[]
#         if phi_analysis:
#             for ii,i in enumerate(phi):
#                     #roi_nr.append(get_roi_nr(total_res['qval_dict'],q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
#                     roi_nr.append(get_roi_nr(roi_dict,q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
#             #Q_str=str(extract_dict['q_dictionary'][roi_nr[ii]][0])
#             Q_str=str(extract_dict['q_dictionary'][roi_nr[ii]][0])
#         else:
#             phi=[-999]
#             phi_nr=[0]
#             Q_str=str(extract_dict['q_dictionary'][q][0])
#             #title_str=' Q= '+str(extract_dict[u]['q_dictionary'][q])+' $\AA^{-1} $'
#         raw_data[Q_str]={}
#         boundaries[Q_str]={}
#         for ph in phi_nr:
#             #exclude_list=[]
#             if phi_analysis:
#                 roi_nr=[]
#                 for i in phi:
#                     #roi_nr.append(get_roi_nr(total_res[list( suid_dict.keys() )[0]]['qval_dict'],Q_nr,i,q_nr=True,phi_nr=False, silent=True)[0])
#                     #roi_nr.append(get_roi_nr(total_res['qval_dict'],q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
#                     roi_nr.append(get_roi_nr(roi_dict,q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
#                 if verbose:
#                     print('ROI number: %s'%roi_nr)
#                 try:
#                     title_str='ROI#: '+str(roi_nr[ph])+'  Q= '+str(extract_dict['q_dictionary'][roi_nr[ph]][0])+' $\AA^{-1}$ \n  $\Phi=$'+str(extract_dict['q_dictionary'][roi_nr[ph]][1])+' -> paral. extrusion'
#                 except:
#                     title_str='ROI#: '+str(roi_nr[ph])+'  Q= '+str(extract_dict['q_dictionary'][roi_nr[ph]][0])+' $\AA^{-1} $'
#             else: 
#                  title_str=' Q= '+str(extract_dict['q_dictionary'][q])+' $\AA^{-1} $'
#             raw_data[Q_str][str(phi[ph])]={}
#             boundaries[Q_str][str(phi[ph])]={}
#             if auto_determine_datasets:
#                 for i in range(len(extract_dict['age_time'])):
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]={}
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['t_zero']=extract_dict['md']['t_zero']
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['tt_zero']=extract_dict['md']['tt_zero']
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['age_width']=extract_dict['age_width'][i]
#                     if phi_analysis:
#                         x=extract_dict['taus_aged'][(roi_nr[ph]*len(extract_dict['age_time']))+i]
#                         y=extract_dict['g2_aged'][(roi_nr[ph]*len(extract_dict['age_time']))+i]
#                     else: 
#                         x=extract_dict['taus_aged'][q*len(extract_dict['age_time'])+i]
#                         y=extract_dict['g2_aged'][q*len(extract_dict['age_time'])+i]
#                     real_ind=np.logical_not(np.isnan(x))*np.logical_not(np.isnan(y))# remove Nan for fit function and '0' time point
#                     x=x[real_ind];y=y[real_ind];x=x[1:];y=y[1:]
#                     if log_resampling:  # Change sampling, if requested
#                     ###########################################################################
#                         try:
#                             [x,y]=lin2log_g2(lin_tau=x,lin_g2=y)
#                         except:
#                             print('failed to apply logarithmic sampling')
#                     if filtering:
#                         x,y=butterworth_filter(x,y,3,.35)
#                     if plotting:
#                         fig,ax2=plt.subplots(1,3,figsize=(12,3))
#                         plt.subplot(1,3,1)
#                         plt.title(title_str)
#                         plt.semilogx(x,y,'ko',fillstyle='none',label='['+str(i)+'] t='+str(np.round(extract_dict['age_time'][i]-extract_dict['md']['tt_zero'],2))+'$\pm$'+str(np.round(extract_dict['age_width'][i]/2,2))+'s')   
#                         plt.xlabel(r'$\tau$ [s]');plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)')
#                     raw_data[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]={'x_dat':x,'y_dat':y}
#                     #a0=y[0];c0=1;d0=np.average(y[-6]);b0=1/(2*x[np.argmin(np.abs(y-0.5*(a0-d0)))])
#                     #p0=[a0,b0,c0,d0]
#                     #bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
#                     #adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
#                     try:
#                         a0=y[0];c0=1;d0=np.average(y[-6]);b0=1/(2*x[np.argmin(np.abs(y-0.5*(a0-d0)))])
#                         p0=[a0,b0,c0,d0]
#                         bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
#                         adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
#                         #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
#                         popt, pcov = curve_fit(g2_fit_func, x, y , p0= p0,bounds=bounds)
#                         #########################################################################################                
#                         perr = np.sqrt(np.diag(pcov))
#                         x_start=np.min(x);x_stop=np.max(x)
#                         x_num=int((np.log10(x_stop)-np.log10(x_start))*10)
#                         xplot=np.logspace(np.log10(x_start)-.5,np.log10(x_stop)+.5,x_num)
#                         r2=np.round(R_2(y,g2_fit_func(x, *popt)),4)
#                         if plotting:
#                             plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
#                             #perr = np.sqrt(np.diag(pcov))
#                             plt.legend(fontsize=8)
#                             plt.subplot(1,3,2)
#                             plt.title('MAD test')
#                         pp=y-g2_fit_func(x, *popt)
#                         out_index=is_outlier(points=pp)
#                         if r2 > MAD_thresh:   # don't remove outliers, if R2 is above threshold for MAD test
#                             out_index=np.zeros(len(out_index), dtype=bool)
#                             if plotting:
#                                 plt.title('MAD test\nR2 > %s: skipped!'%MAD_thresh)
#                         if plotting:
#                             plt.semilogx(x,y-g2_fit_func(x, *popt)-np.mean(y-g2_fit_func(x, *popt)),'ko')
#                             plt.semilogx(x,np.median(pp)*np.ones(np.shape(pp)),'g--',linewidth=4)
#                             plt.xlabel(r'$\tau$ [s]')
#                     except:
#                         print("initial fit didn't converge...setting R2 to -999!")
#                         r2=-99999
#                     bound_results={}    ######
#                     prelim_fit_params={}
#                     if r2 > r2_thresh:
#                         done=True
#                         if plotting:
#                             plt.semilogx(x[out_index],pp[out_index],'r^')
#                         p0=[popt[0],popt[1],popt[2],popt[3]]
#                         bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
#                         adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
#                         #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
#                         popt, pcov = curve_fit(g2_fit_func, x[np.invert(out_index)], y[np.invert(out_index)] , p0= p0,bounds=bounds)
#                         #########################################################################################
#                         r2=np.round(R_2(y[np.invert(out_index)],g2_fit_func(x[np.invert(out_index)], *popt)),4)
#                         perr = np.sqrt(np.diag(pcov))
#                         prelim_fit_params={'beta':popt[0],'beta_err':perr[0],'Gamma':popt[1],'Gamma_err':perr[1],'gamma':popt[2],'gamma_err':perr[2],'base':popt[3],'base_err':perr[3]}
#                         if len(y[np.invert(out_index)])>10:
#                             R2_contrast=np.round(R_2(y[np.invert(out_index)][:10],g2_fit_func(x[np.invert(out_index)][:10], *popt)),4)
#                             R2_baseline=np.round(R_2(y[np.invert(out_index)][-10:],g2_fit_func(x[np.invert(out_index)][-10:], *popt)),4)
#                         else:
#                             R2_contrast=r2;R2_baseline=r2
#                         bound_results['outliers']=out_index
#                         bound_results['R2']={'R2':r2,'R2_contrast':R2_contrast,'R2_baseline':R2_baseline}
#                         [contrast,baseline]=c_b_finder(a=popt[0],b=popt[1],c=popt[2],d=popt[3],taus=x[np.invert(out_index)],fine_scale=1,contrast_points=contrast_points,base_slope=base_slope, verbose=verbose)
#                         #print(title_str+' contrast: %s  baseline: %s'%(contrast,baseline))
#                         #print('R2_contrast: %s  r2_contrast_thresh: %s'%(R2_contrast,r2_contrast_thresh))
#                         if plotting:
#                             plt.subplot(1,3,3)
#                             plt.title('R^2 contrast: %s  \nR^2 baseline: %s'%(np.round(R2_contrast,4),np.round(R2_baseline,4)))
#                             plt.semilogx(x[np.invert(out_index)],y[np.invert(out_index)],'ko',fillstyle='none')
#                             plt.xlabel(r'$\tau$ [s]');plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)')
#                             plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
#                         if contrast=='not_determined':
#                             done=False
#                             bound_results['contrast']=contrast
#                             cc='';vis=False
#                             if plotting:
#                                 plt.semilogx([-1000,-100],[np.mean(y[np.invert(out_index)]),np.mean(y[np.invert(out_index)])],cc,visible=vis,label='auto-contrast: N.A.')
#                         elif contrast!='not_determined' and R2_contrast >= r2_contrast_thresh:
#                             bound_results['contrast']=contrast
#                             cc='m--';vis=True
#                             if plotting:
#                                 plt.semilogx([np.min(xplot),np.max(xplot)],[popt[3]+contrast,popt[3]+contrast],cc,label='auto-contrast: %s'%np.round(contrast,4))
#                         else:
#                             bound_results['contrast']='not_determined'
#                             contrast='not_determined'
#                             done=False
#                         if baseline=='not_determined':
#                             done=False
#                             bound_results['baseline']=baseline
#                             cc='';vis=False
#                             if plotting:
#                                 plt.semilogx([-1000,-100],[np.mean(y[np.invert(out_index)]),np.mean(y[np.invert(out_index)])],cc,visible=vis,label='auto-baseline: N.A.')
#                         else:
#                             bound_results['baseline']=baseline
#                             cc='c--';vis=True
#                             if plotting:
#                                 plt.semilogx([np.min(xplot),np.max(xplot)],[baseline,baseline],cc,visible=vis,label='auto-baseline: %s'%np.round(baseline,4))
#                         if plotting:
#                             plt.legend(fontsize=8,loc=7)
#                         if done:
#                             bound_results['status']='complete'
#                             bound_results['ini_status']='complete'
#                         else:
#                             bound_results['status']='incomplete'
#                             bound_results['ini_status']='incomplete'
#                         if baseline=='not_determined' and contrast=='not_determined':
#                             bound_results['status']='not_fitable'
#                             bound_results['ini_status']='not_fitable'
#                     else:
#                         bound_results['status']='not_fitable'
#                         bound_results['ini_status']='not_fitable'
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['bound_results']=bound_results
#                     boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['prelim_fit_params']=prelim_fit_params
#                     if plotting:
#                         plt.tight_layout()    
#     return [raw_data,boundaries]
def initial_fit(total_res,extract_dict,phi_analysis,phi,phi_nr,Q_nr,r2_thresh = .8,verbose=False,plotting=False, *argv, **kwargs):
    """
    function for initial fit of  dataset
    total_res -> loaded hdf5 file from XPCS_Single
    extract_dict -> loaded hdf5 with aged g2s
    returns: [raw_data,boundatries]
    """
        
    if 'MAD_thresh' in kwargs.keys():
        MAD_thresh= kwargs['MAD_thresh']
    else:
        MAD_thresh=1
    if 'contrast_points' in kwargs.keys():
        contrast_points=kwargs['contrast_points']
    else: contrast_points=4
    if 'base_slope' in kwargs.keys():
        base_slope=kwargs['base_slope']
    else: base_slope=.001
    if 'gisaxs' in kwargs.keys():
        gisaxs_analysis=kwargs['gisaxs']
    else: gisaxs_analysis = False
            
    
    auto_determine_datasets=True # at this point, there is no manual option...
    
    if not verbose:
        print('Note: "verbose=False" -> text output is off')
    if not plotting:
        print('Note: "plotting=False" -> plots are off')
    r2_contrast_thresh = -999 # it's programed in, but not sure how to use it: flat contrast region doesn't give a good R2...(same problem with baseline, for which currently no R2 is implemented)
    # new: ensure that ROI assignment is correct...there was a discrepancy with ordering in total_res and extract_dict for data processed on xf11id-srv2
    roi_dict={}
    for ii,i in enumerate(extract_dict['q_dictionary']):
        roi_dict[ii]=i
    raw_data={}
    boundaries={}
    for q in Q_nr:
        roi_nr=[]
        if phi_analysis:
            for ii,i in enumerate(phi):
                    #roi_nr.append(get_roi_nr(total_res['qval_dict'],q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
                    roi_nr.append(get_roi_nr(roi_dict,q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
            #Q_str=str(extract_dict['q_dictionary'][roi_nr[ii]][0])
            Q_str=str(extract_dict['q_dictionary'][roi_nr[ii]][0])
        else:
            phi=[-999]
            phi_nr=[0]
            Q_str=str(sorted(extract_dict['q_dictionary'])[q][0])
            #title_str=' Q= '+str(extract_dict[u]['q_dictionary'][q])+' $\AA^{-1} $'
        raw_data[Q_str]={}
        boundaries[Q_str]={}
        for ph in phi_nr:
            #exclude_list=[]
            if phi_analysis:
                roi_nr=[]
                for i in phi:
                    #roi_nr.append(get_roi_nr(total_res[list( suid_dict.keys() )[0]]['qval_dict'],Q_nr,i,q_nr=True,phi_nr=False, silent=True)[0])
                    #roi_nr.append(get_roi_nr(total_res['qval_dict'],q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
                    roi_nr.append(get_roi_nr(roi_dict,q,i,q_nr=True,phi_nr=False, q_thresh=1E-4, p_thresh=1E-4,silent=True)[0])
                if verbose:
                    print('ROI number: %s'%roi_nr)
                try:
                    title_str='ROI#: '+str(roi_nr[ph])+'  Q= '+str(extract_dict['q_dictionary'][roi_nr[ph]][0])+' $\AA^{-1}$ \n  $\Phi=$'+str(extract_dict['q_dictionary'][roi_nr[ph]][1])+' -> paral. extrusion'
                except:
                    title_str='ROI#: '+str(roi_nr[ph])+'  Q= '+str(extract_dict['q_dictionary'][roi_nr[ph]][0])+' $\AA^{-1} $'
            else: 
                 title_str=' Q= '+str(sorted(extract_dict['q_dictionary'])[q][0])+' $\AA^{-1} $'
            raw_data[Q_str][str(phi[ph])]={}
            boundaries[Q_str][str(phi[ph])]={}
            if auto_determine_datasets:
                for i in range(len(extract_dict['age_time'])):
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]={}
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['t_zero']=extract_dict['md']['t_zero']
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['tt_zero']=extract_dict['md']['tt_zero']
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['age_width']=extract_dict['age_width'][i]
                    if phi_analysis:
                        x=extract_dict['taus_aged'][(roi_nr[ph]*len(extract_dict['age_time']))+i]
                        y=extract_dict['g2_aged'][(roi_nr[ph]*len(extract_dict['age_time']))+i]
                    else: 
                        x=extract_dict['taus_aged'][q*len(extract_dict['age_time'])+i]
                        y=extract_dict['g2_aged'][q*len(extract_dict['age_time'])+i]
                    real_ind=np.logical_not(np.isnan(x))*np.logical_not(np.isnan(y))# remove Nan for fit function and '0' time point
                    x=x[real_ind];y=y[real_ind];x=x[1:];y=y[1:]
                    if log_resampling:  # Change sampling, if requested
                    ###########################################################################
                        try:
                            [x,y]=lin2log_g2(lin_tau=x,lin_g2=y)
                        except:
                            print('failed to apply logarithmic sampling')
                    if filtering:
                        x,y=butterworth_filter(x,y,3,.35)
                    if plotting:
                        fig,ax2=plt.subplots(1,3,figsize=(12,3))
                        plt.subplot(1,3,1)
                        plt.title(title_str)
                        plt.semilogx(x,y,'ko',fillstyle='none',label='['+str(i)+'] t='+str(np.round(extract_dict['age_time'][i]-extract_dict['md']['tt_zero'],2))+'$\pm$'+str(np.round(extract_dict['age_width'][i]/2,2))+'s')   
                        plt.xlabel(r'$\tau$ [s]');plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)')
                    raw_data[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]={'x_dat':x,'y_dat':y}
                    #a0=y[0];c0=1;d0=np.average(y[-6]);b0=1/(2*x[np.argmin(np.abs(y-0.5*(a0-d0)))])
                    #p0=[a0,b0,c0,d0]
                    #bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
                    #adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
                    try:
                        a0=y[0];c0=1;d0=np.average(y[-6]);b0=1/(2*x[np.argmin(np.abs(y-0.5*(a0-d0)))])
                        p0=[a0,b0,c0,d0]
                        bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
                        adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
                        #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
                        popt, pcov = curve_fit(g2_fit_func, x, y , p0= p0,bounds=bounds)
                        #########################################################################################                
                        perr = np.sqrt(np.diag(pcov))
                        x_start=np.min(x);x_stop=np.max(x)
                        x_num=int((np.log10(x_stop)-np.log10(x_start))*10)
                        xplot=np.logspace(np.log10(x_start)-.5,np.log10(x_stop)+.5,x_num)
                        r2=np.round(R_2(y,g2_fit_func(x, *popt)),4)
                        if plotting:
                            plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
                            #perr = np.sqrt(np.diag(pcov))
                            plt.legend(fontsize=8)
                            plt.subplot(1,3,2)
                            plt.title('MAD test')
                        pp=y-g2_fit_func(x, *popt)
                        out_index=is_outlier(points=pp)
                        if r2 > MAD_thresh:   # don't remove outliers, if R2 is above threshold for MAD test
                            out_index=np.zeros(len(out_index), dtype=bool)
                            if plotting:
                                plt.title('MAD test\nR2 > %s: skipped!'%MAD_thresh)
                        if plotting:
                            plt.semilogx(x,y-g2_fit_func(x, *popt)-np.mean(y-g2_fit_func(x, *popt)),'ko')
                            plt.semilogx(x,np.median(pp)*np.ones(np.shape(pp)),'g--',linewidth=4)
                            plt.xlabel(r'$\tau$ [s]')
                    except:
                        print("initial fit didn't converge...setting R2 to -999!")
                        r2=-99999
                    bound_results={}    ######
                    prelim_fit_params={}
                    if r2 > r2_thresh:
                        done=True
                        if plotting:
                            plt.semilogx(x[out_index],pp[out_index],'r^')
                        p0=[popt[0],popt[1],popt[2],popt[3]]
                        bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])
                        adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
                        #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
                        popt, pcov = curve_fit(g2_fit_func, x[np.invert(out_index)], y[np.invert(out_index)] , p0= p0,bounds=bounds)
                        #########################################################################################
                        r2=np.round(R_2(y[np.invert(out_index)],g2_fit_func(x[np.invert(out_index)], *popt)),4)
                        perr = np.sqrt(np.diag(pcov))
                        prelim_fit_params={'beta':popt[0],'beta_err':perr[0],'Gamma':popt[1],'Gamma_err':perr[1],'gamma':popt[2],'gamma_err':perr[2],'base':popt[3],'base_err':perr[3]}
                        if len(y[np.invert(out_index)])>10:
                            R2_contrast=np.round(R_2(y[np.invert(out_index)][:10],g2_fit_func(x[np.invert(out_index)][:10], *popt)),4)
                            R2_baseline=np.round(R_2(y[np.invert(out_index)][-10:],g2_fit_func(x[np.invert(out_index)][-10:], *popt)),4)
                        else:
                            R2_contrast=r2;R2_baseline=r2
                        bound_results['outliers']=out_index
                        bound_results['R2']={'R2':r2,'R2_contrast':R2_contrast,'R2_baseline':R2_baseline}
                        [contrast,baseline]=c_b_finder(a=popt[0],b=popt[1],c=popt[2],d=popt[3],taus=x[np.invert(out_index)],fine_scale=1,contrast_points=contrast_points,base_slope=base_slope, verbose=verbose)
                        #print(title_str+' contrast: %s  baseline: %s'%(contrast,baseline))
                        #print('R2_contrast: %s  r2_contrast_thresh: %s'%(R2_contrast,r2_contrast_thresh))
                        if plotting:
                            plt.subplot(1,3,3)
                            plt.title('R^2 contrast: %s  \nR^2 baseline: %s'%(np.round(R2_contrast,4),np.round(R2_baseline,4)))
                            plt.semilogx(x[np.invert(out_index)],y[np.invert(out_index)],'ko',fillstyle='none')
                            plt.xlabel(r'$\tau$ [s]');plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)')
                            plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
                        if contrast=='not_determined':
                            done=False
                            bound_results['contrast']=contrast
                            cc='';vis=False
                            if plotting:
                                plt.semilogx([-1000,-100],[np.mean(y[np.invert(out_index)]),np.mean(y[np.invert(out_index)])],cc,visible=vis,label='auto-contrast: N.A.')
                        elif contrast!='not_determined' and R2_contrast >= r2_contrast_thresh:
                            bound_results['contrast']=contrast
                            cc='m--';vis=True
                            if plotting:
                                plt.semilogx([np.min(xplot),np.max(xplot)],[popt[3]+contrast,popt[3]+contrast],cc,label='auto-contrast: %s'%np.round(contrast,4))
                        else:
                            bound_results['contrast']='not_determined'
                            contrast='not_determined'
                            done=False
                        if baseline=='not_determined':
                            done=False
                            bound_results['baseline']=baseline
                            cc='';vis=False
                            if plotting:
                                plt.semilogx([-1000,-100],[np.mean(y[np.invert(out_index)]),np.mean(y[np.invert(out_index)])],cc,visible=vis,label='auto-baseline: N.A.')
                        else:
                            bound_results['baseline']=baseline
                            cc='c--';vis=True
                            if plotting:
                                plt.semilogx([np.min(xplot),np.max(xplot)],[baseline,baseline],cc,visible=vis,label='auto-baseline: %s'%np.round(baseline,4))
                        if plotting:
                            plt.legend(fontsize=8,loc=7)
                        if done:
                            bound_results['status']='complete'
                            bound_results['ini_status']='complete'
                        else:
                            bound_results['status']='incomplete'
                            bound_results['ini_status']='incomplete'
                        if baseline=='not_determined' and contrast=='not_determined':
                            bound_results['status']='not_fitable'
                            bound_results['ini_status']='not_fitable'
                    else:
                        bound_results['status']='not_fitable'
                        bound_results['ini_status']='not_fitable'
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['bound_results']=bound_results
                    boundaries[Q_str][str(phi[ph])][str(extract_dict['age_time'][i])]['prelim_fit_params']=prelim_fit_params
                    if plotting:
                        plt.tight_layout()    
    return [raw_data,boundaries]


def consecutive_fitting(raw_data,boundaries,phi_analysis,phi,uid,r2_thresh = .8,verbose=False,plotting=False,overview=True, *argv, **kwargs):
    """
    optional argument: failed_fit_final=True/False -> if True: mark failed fit as 'not_fitable', if False: mark failed fit as 'masked', default=True
    """
    # successive fitting for incomplete datasets:
    
    if 'include_Phi' in kwargs:
        include_Phi = kwargs['include_Phi']
    else:
        include_Phi = False
    
    if 'failed_fit_final' in kwargs.keys():
        failed_fit_final = kwargs['failed_fit_final']
    else:
        failed_fit_final = True
    
    if 'MAD_thresh' in kwargs.keys():
        MAD_thresh= kwargs['MAD_thresh']
    else:
        MAD_thresh=1
    
    if 'comp_percent' in kwargs.keys():
        comp_percent= kwargs['comp_percent']
    else:
        comp_percent=0
    
    if not phi_analysis:
        phi=[-999]
        phi_nr=[0]
    
    in_ct=0
    c=incomplete_cts(boundaries,verbose=verbose)
    for i in list(c.keys()):
        in_ct=in_ct+c[i]
    previous_in_ct=in_ct+1
    
    modi_index=[]
    
    while previous_in_ct > in_ct:
        #print('START of while loop: previous_in_ct=%s | in_ct=%s'%( previous_in_ct,in_ct))
        print('previous number of incomplete fits dataset: %s / current number: %s  -> continue trying to fit incomplete datasets!'%(previous_in_ct,in_ct))

        next_fit = find_most_neighbours(complete_neighbours(boundaries,include_Phi=include_Phi))
        
        modification_ct=0
        for i in list(next_fit.keys()):            
            #modification_ct=0
            if next_fit[i]:  # empty dictionary condition
                if phi_analysis:
                    modi_index.append([float(i),float(next_fit[i]['Q']),float(next_fit[i]['t_age'])
                                       -boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['t_zero']])
                else:
                    modi_index.append([float(i),float(next_fit[i]['Q']),float(next_fit[i]['t_age'])])
                modification_ct=1
                if plotting:
                    fig,ax=plt.subplots(1,3,figsize=(12,4))
                x=raw_data[next_fit[i]['Q']][i][next_fit[i]['t_age']]['x_dat']
                y=raw_data[next_fit[i]['Q']][i][next_fit[i]['t_age']]['y_dat']
                a0=y[0];c0=1;d0=np.average(y[-6]);b0=1/(2*x[np.argmin(np.abs(y-0.5*(a0-d0)))]) # -> generic start values, overwrite below with what exists
                ini_status=boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['ini_status']
                if boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['contrast'] == 'not_determined':
                    exist_key='baseline';d0=boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]
                    mis_key='contrast';a0=np.mean(next_fit[i][mis_key])

                elif boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['baseline'] == 'not_determined':
                    exist_key='contrast';a0=boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]
                    mis_key='baseline';d0=np.mean(next_fit[i][mis_key])
                # check whether existing baseline or contrast matches interval determined by the neighbours:
#                print('exist_key: ',exist_key)
#                print('next_fit[i]: ',next_fit[i])
#                print("next_fit[i]['Q']][i][next_fit[i]['t_age']: ",next_fit[i],['Q'],[i],next_fit[i],['t_age'])
#                print("boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]-1: ",boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key])
                if (exist_key=='contrast' and boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key] *(1+comp_percent) >= np.min(next_fit[i][exist_key]) and boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]*(1-comp_percent) <= np.max(next_fit[i][exist_key])) or (exist_key=='baseline' and 1+(boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]-1) *(1+comp_percent) >= np.min(next_fit[i][exist_key]) and 1+(boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]-1) *(1-comp_percent) <= np.max(next_fit[i][exist_key])): 
                    if verbose:
                        print('previously determined '+exist_key+': %s'%boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]+' compatible with neighbours: [%s, %s]'%(np.min(next_fit[i][exist_key]),np.max(next_fit[i][exist_key])))
                    p0=[a0,b0,c0,d0]
                    if mis_key=='contrast':
                        bounds=([np.min(next_fit[i][mis_key])*(1-comp_percent),1E-8,.5,.95],[np.max(next_fit[i][mis_key])*(1+comp_percent),5E4,2.,1.5])   # first fit, imposing peer bounds
                    elif mis_key=='baseline':
                        bounds=([0.001,1E-8,.5,np.min(next_fit[i][mis_key])],[2,5E4,2.,np.max(next_fit[i][mis_key])])
                    adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
                    #adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='bounds')
                    #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
                    popt, pcov = curve_fit(g2_fit_func, x, y , p0= p0,bounds=bounds)
                    #########################################################################################
                    perr = np.sqrt(np.diag(pcov))
                    x_start=np.min(x);x_stop=np.max(x)
                    x_num=int((np.log10(x_stop)-np.log10(x_start))*10)
                    xplot=np.logspace(np.log10(x_start)-2,np.log10(x_stop)+2,x_num)
        #                xplot=np.logspace()
                    r2=np.round(R_2(y,g2_fit_func(x, *popt)),4)
                    if plotting:
                        plt.subplot(1,3,1)
                        plt.semilogx(x,y,'ko',fillstyle='none')
                        plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
                        plt.title('Q: %s \nPhi: %s  t_age: %s'%(next_fit[i]['Q'],i,next_fit[i]['t_age']))
                        plt.legend(fontsize=8)
                    pp=y-g2_fit_func(x, *popt)
                    out_index=is_outlier(points=pp)
                    if r2 > MAD_thresh:   # don't remove outliers, if R2 is above threshold for MAD test
                        out_index=np.zeros(len(out_index), dtype=bool)
                    if plotting:
                        plt.subplot(1,3,2)
                        plt.semilogx(x,y-g2_fit_func(x, *popt)-np.mean(y-g2_fit_func(x, *popt)),'ko')
                        plt.semilogx(x,np.median(pp)*np.ones(np.shape(pp)),'g--',linewidth=4)
                    #ini_status=bound_results['ini_status']
                    bound_results={}
                    prelim_fit_params={}
                    if r2 > r2_thresh:
                        if plotting:
                            plt.semilogx(x[out_index],pp[out_index],'r^')#-np.mean(y[out_index]-g2_fit_func(x[out_index], *popt)),'r^')
        #             #plt.semilogx(x,np.mean(y-g2_fit_func(x, *popt)),'ko')
                        p0=[popt[0],popt[1],popt[2],popt[3]]
                        #bounds=([0.001,1E-8,.5,.95],[2,5E4,2.,1.5])                           # second fit, imposing same boundaries from peers as before....
                        adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
                        #print('Q: %s Phi: %s t_age: %s',next_fit[i]['Q'],i,next_fit[i]['t_age'])
                        #print('bounds for second fit: ',bounds)
                        #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
                        popt, pcov = curve_fit(g2_fit_func, x[np.invert(out_index)], y[np.invert(out_index)] , p0= p0,bounds=bounds)
                        #########################################################################################
                        #print('BASELINE FROM FIT : ',popt[3])
                        r2=np.round(R_2(y[np.invert(out_index)],g2_fit_func(x[np.invert(out_index)], *popt)),4)
                        perr = np.sqrt(np.diag(pcov))
                        prelim_fit_params={'beta':popt[0],'beta_err':perr[0],'Gamma':popt[1],'Gamma_err':perr[1],'gamma':popt[2],'gamma_err':perr[2],'base':popt[3],'base_err':perr[3]}
                        if len(y[np.invert(out_index)])>10:
                            R2_contrast=np.round(R_2(y[np.invert(out_index)][:10],g2_fit_func(x[np.invert(out_index)][:10], *popt)),4)
                            R2_baseline=np.round(R_2(y[np.invert(out_index)][-10:],g2_fit_func(x[np.invert(out_index)][-10:], *popt)),4)
                        else:
                            R2_contrast=r2;R2_baseline=r2
                        bound_results['outliers']=out_index
                        bound_results['R2']={'R2':r2,'R2_contrast':R2_contrast,'R2_baseline':R2_baseline}
                        #[contrast,baseline]=c_b_finder(a=popt[0],b=popt[1],c=popt[2],d=popt[3],taus=x[np.invert(out_index)],fine_scale=1,contrast_points=4,base_slope=.001)
                        if plotting:
                            plt.subplot(1,3,3)
                            plt.title('R^2 contrast: %s  \nR^2 baseline: %s'%(np.round(R2_contrast,4),np.round(R2_baseline,4)))
                            plt.semilogx(x[np.invert(out_index)],y[np.invert(out_index)],'ko',fillstyle='none')
                            plt.semilogx(xplot ,g2_fit_func(xplot, *popt),'r--',label='R^2 = %s'%r2)
                            plt.semilogx([np.min(xplot),np.max(xplot)],[popt[0]+popt[3],popt[0]+popt[3]],'m--',linewidth=3,label='contrast: %s'%popt[0])
                            plt.semilogx([np.min(xplot),np.max(xplot)],[popt[3]+popt[0]/2,popt[3]+popt[0]/2],'k--',linewidth=2)
                            plt.semilogx([np.min(xplot),np.max(xplot)],[popt[3],+popt[3]],'g--',linewidth=3)
                            plt.legend(fontsize=8)
                        if np.max(y[np.invert(out_index)]) >= popt[3]+popt[0]/2 and np.min(y[np.invert(out_index)]) <= popt[3]+popt[0]/2:
                            if verbose:
                                print('Have more than half of the decay of the correlation function -> accept fit!')
                            bound_results['status']='complete';bound_results['contrast']=popt[0];bound_results['baseline']=popt[3]
                        else:
                            if verbose:
                                print('Do NOT have more than half of the decay of the correlation function -> discard fit')
                                print('not_fitable')        ####################################### need to change
                            if failed_fit_final:
                                bound_results={};bound_results['status']='not_fitable'
                                prelim_fit_params={}
                            else:
                                bound_results['status']='masked'
                    else:
                        if verbose:
                            print('not_fitable')
                        if failed_fit_final:
                                bound_results={};bound_results['status']='not_fitable'
                                prelim_fit_params={}
                        else:
                            bound_results['status']='masked'  
                else:
                    if verbose:
                        print('previously determined '+exist_key+': %s'%boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results'][exist_key]+' NOT compatible with neighbours: [%s, %s]'%(np.min(next_fit[i][exist_key]),np.max(next_fit[i][exist_key])))
                        print('not_fitable')
                    if failed_fit_final:
                                bound_results={};bound_results['status']='not_fitable'
                                prelim_fit_params={}
                    else:
                        bound_results={};bound_results['status']='masked'
                if verbose:
                    print('bound_results: ',bound_results)
                    print('prelim_fitresults: ', prelim_fit_params)
                ####   need to update boudaries dictionary here !!!
                # plt.title('Q: %s \nPhi: %s  t_age: %s'%(next_fit[i]['Q'],i,next_fit[i]['t_age']))
                if bound_results['status'] == 'masked':
                    boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['status']=bound_results['status']
                    boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['ini_status']=ini_status
                else:
                    boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']=bound_results
                    boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['bound_results']['ini_status']=ini_status
                    boundaries[next_fit[i]['Q']][i][next_fit[i]['t_age']]['prelim_fit_params']=prelim_fit_params
        if modification_ct==0:
            if verbose:
                if failed_fit_final:
                    print('no more points to fit...-> setting any remaining "incomplete" fits to "not_fitable"')
                else:
                    print('no more points to fit...-> setting any remaining "incomplete" fits to "masked"')
            if failed_fit_final:
                incomplete_cts(boundaries,set_not_fitable=True,verbose=verbose)
            else:
                incomplete_cts(boundaries,set_not_fitable=True,verbose=verbose,marker_str='masked')
        # check new numbers: are we reducing the number of datasets with incomplete fitting?
        previous_in_ct=in_ct
        c=incomplete_cts(boundaries, verbose=verbose)
        in_ct=0    ##################################################################################   !!!!!!!!!!!!!!!!!!!!!!!!
        for i in list(c.keys()):
            in_ct=in_ct+c[i]
        #print('END of while loop: previous_in_ct=%s | in_ct=%s'%( previous_in_ct,in_ct))
        if overview and in_ct!=0:
            plot_fit_boundaries(boundaries,uid,phi_analysis,phi)
            for l in range(len(modi_index)):
                if modi_index[l][0]==phi[0]:
                    plt.subplot(1,2,1)
                    plt.plot(modi_index[l][2],modi_index[l][1],'ko',fillstyle='none',markersize=12)
                elif modi_index[l][0]==phi[1]:
                    plt.subplot(1,2,2)
                    plt.plot(modi_index[l][2],modi_index[l][1],'ko',fillstyle='none',markersize=12)
    if overview:
        plot_fit_boundaries(boundaries,uid,phi_analysis,phi)
        for l in range(len(modi_index)):
                if modi_index[l][0]==phi[0]:
                    plt.subplot(1,2,1)
                    plt.plot(modi_index[l][2],modi_index[l][1],'ko',fillstyle='none',markersize=12)
                elif modi_index[l][0]==phi[1]:
                    plt.subplot(1,2,2)
                    plt.plot(modi_index[l][2],modi_index[l][1],'ko',fillstyle='none',markersize=12)
    return boundaries

def c_b_finder(a,b,c,d,taus,fine_scale=1,contrast_points=4,base_slope=.001,plotting=False,verbose=True):
    """
    function determines baseline and contrast from correlation function data (intended to work on fit, not on raw data!) 
    """
    x_start=np.min(taus)
    x_stop=np.max(taus)
    #fine_scale=1 # increase sampling of 10 points / decade by scaling factor

    x_num=int(fine_scale*(np.log10(x_stop)-np.log10(x_start))*10)

    tx=np.logspace(np.log10(x_start),np.log10(x_stop),x_num)

    
    from scipy.optimize import curve_fit
    #from scipy.signal import argrelextrema

    #def g2_fit_func(x, a, b, c, d):
    #    return a*np.exp( -2*(b*x)**c) +d    # a -> beta; b -> Gamma; c-> gamma; d-> baseline
    
    contrast_point=contrast_points*fine_scale
    if plotting:
        fig99,ax99=plt.subplots(1,4,figsize=(18,2))
        plt.subplot(1,4,1)
        plt.semilogx(tx,g2_fit_func(tx, a, b, c, d),'ko--')
    n=1
    dif = np.diff(g2_fit_func(tx, a, b, c, d),n=n)/(tx[1]-tx[0])
    if plotting:
        plt.subplot(1,4,2) # first derivative: looking for contrast
        plt.semilogx(tx[:-n],dif)
    min_ind=np.argmin(dif)
    if plotting:
        plt.plot(tx[:-n][np.argmin(dif)],dif[np.argmin(dif)],'r+',Markersize=15,markeredgewidth=4)
    if np.argmin(dif) >=contrast_points: # and np.argmin(dif) < len(dif)-contrast_points:
        if verbose:
            print('local minimum at tau index #',np.argmin(dif),' -> can use contrast from this function')
        contrast = a
    else:
        if verbose:
            print('local minimum at tau index #',np.argmin(dif),' -> can NOT use contrast from this function')
        contrast = 'not_determined'

    #base_slope= 0.001   
    base_ind=np.abs(dif[min_ind:]) <= base_slope
    if any(x == True for x in base_ind):
        if verbose:
            print('baseline slope < ',base_slope,' -> can use baseline from this function')
        if plotting:
            plt.semilogx(tx[:-n][min_ind:][base_ind],dif[min_ind:][base_ind],'g+',Markersize=15,markeredgewidth=4)
            plt.subplot(1,4,1)
            plt.plot(tx[min_ind:][base_ind.tolist().index(True) ],g2_fit_func(tx[min_ind:][base_ind.tolist().index(True) ], a, b, c, d),'g+-',Markersize=15,markeredgewidth=4)
        baseline = d
    else:
        if verbose:
            print('baseline slope > ',base_slope,' -> can NOT use baseline from this function')
        baseline = 'not_determined'
    if plotting:    
        plt.subplot(1,4,1)
        plt.plot(tx[np.argmin(dif)-contrast_points],g2_fit_func(tx[np.argmin(dif)-contrast_points], a, b, c, d),'r+',Markersize=15,markeredgewidth=4)

    return [contrast,baseline]

def update_boundaries_from_man_fit(use_re_fitted, discard, manfit_dict, man_fit_result_dict, index_dict, boundaries):
    u = list(manfit_dict.keys())[0]
    for i in use_re_fitted:
        q=index_dict[u][str(i)]['Q'];p=index_dict[u][str(i)]['Phi'];t=index_dict[u][str(i)]['t_age']
        boundaries[u][q][p][t]['bound_results']['R2']=man_fit_result_dict[u][str(i)]['R2']
        boundaries[u][q][p][t]['bound_results']['status']='complete'
        boundaries[u][q][p][t]['bound_results']['contrast']=man_fit_result_dict[u][str(i)]['prelim_fit_params']['beta']
        boundaries[u][q][p][t]['bound_results']['baseline']=man_fit_result_dict[u][str(i)]['prelim_fit_params']['base']
        boundaries[u][q][p][t]['prelim_fit_params']=man_fit_result_dict[u][str(i)]['prelim_fit_params']
        boundaries[u][q][p][t]['bound_results']['outliers']=man_fit_result_dict[u][str(i)]['outliers']
        #print(boundaries[u][q][p][t]['bound_results'])
        #print(boundaries[u][q][p][t]['prelim_fit_params'])

    if discard:
        remove_data_from_boundaries(boundaries[u],index_dict[u],discard)

def is_outlier(points,thresh=3.5,verbose=False):
    # MAD test
    points.tolist()
    #if np.size(points) ==1:
    if len(points) ==1:
        points=points[:,None]
        if verbose:
            print('input to is_outlier is a single point...')
    median = np.median(points)*np.ones(np.shape(points))#, axis=0)
    #print('median: ',median)
    
    #diff = np.sum((points-median)**2, axis=0)
    diff = (points-median)**2
    diff=np.sqrt(diff)
    #print('diff: ',diff)
    med_abs_deviation= np.median(diff)
    
    modified_z_score = .6745*diff/med_abs_deviation
    
    return modified_z_score > thresh

def manual_fit(manfit_dict,index_dict,boundaries,raw_data,*argv, **kwargs):
    if 'row_scale' in kwargs:
        row_scale = kwargs['row_scale']
    else:
        row_scale = 4
    if 'wspace' in kwargs:
        wspace=kwargs['wspace']
    else:
        wspace=1
    if 'hspace' in kwargs:
        hspace=kwargs['hspace']
    else:
        hspace=.5
        
    u = list(manfit_dict.keys())[0]
    fig,ax=plt.subplots(1,2,figsize=(16,row_scale))
    man_fit_result_dict={}
    man_fit_result_dict[u]={}
    for i in manfit_dict[u]:
        man_fit_result_dict[u][str(i)]={}
        q=index_dict[u][str(i)]['Q'];p=index_dict[u][str(i)]['Phi'];t=index_dict[u][str(i)]['t_age']
        try:  #previous fit exists
            R2_value=boundaries[u][q][p][t]['bound_results']['R2']['R2']
            a=boundaries[u][q][p][t]['prelim_fit_params']['beta']
            b=boundaries[u][q][p][t]['prelim_fit_params']['Gamma']
            c=boundaries[u][q][p][t]['prelim_fit_params']['gamma']
            d=boundaries[u][q][p][t]['prelim_fit_params']['base']
            out_index=boundaries[u][q][p][t]['bound_results']['outliers']
            x=raw_data[u][q][p][t]['x_dat'][np.invert(out_index)];y=raw_data[u][q][p][t]['y_dat'][np.invert(out_index)]
            plot_initial_fit=True
        except: # no previous fit
            plot_initial_fit=False
            R2_value='N.A.'
            a=np.average([manfit_dict['contrast_limit'][0]-(manfit_dict['base_limit'][1]-1),manfit_dict['contrast_limit'][1]-(manfit_dict['base_limit'][0]-1)])
            c=1.4
            d=np.average([manfit_dict['base_limit'][1],manfit_dict['base_limit'][0]])
            x=raw_data[u][q][p][t]['x_dat']
            y=raw_data[u][q][p][t]['y_dat']
            out_index=np.zeros(np.shape(x),dtype='bool')
            try:
                b=1/manfit_dict['tau0']
            except:
                b=1/(2*x[np.argmin(np.abs(y-0.5*(a-d)))])
        try:
            xl=manfit_dict['tau_lim']
            if xl[1]==0:
                xl[1]=len(x)
                sign_xl_max=1
            else:
                sign_xl_max=-1
        except:
            xl=[0,len(x)]
            sign_xl_max=1
            
        plt.subplot(1,2,1)
        cp=plt.semilogx(x,y,'o',label='[%s] R$^2$=%s'%(i,R2_value))
        x_start=np.min(x);x_stop=np.max(x)
        x_num=int((np.log10(x_stop)-np.log10(x_start))*10)
        xplot=np.logspace(np.log10(x_start)-.5,np.log10(x_stop)+.5,x_num)
        color=cp[0].get_color()
        plt.title('uid: '+u[:8]+' Q=%s $\AA^{-1}$'%q[:8])
        if plot_initial_fit:
            plt.semilogx(xplot,g2_fit_func(xplot, a,b,c,d),'-',color=color)
        plt.xlabel(r'$\tau$ [s]',fontsize=14);plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)',fontsize=14)
        plt.grid(b=True)
        ax=plt.gca()
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        ax.legend(fontsize=10,loc='lower left', bbox_to_anchor=(1., 0.0))
        
        p0=[a,b,c,d]
        if manfit_dict['base_limit']:
            base_min=manfit_dict['base_limit'][0]
            base_max=manfit_dict['base_limit'][1]
        else:
            base_min=d*.95;base_max=d*1.05
        if manfit_dict['contrast_limit']:
            con_min=manfit_dict['contrast_limit'][0]
            con_max=manfit_dict['contrast_limit'][1]
        else:
            con_min=a*.95;con_max=a*1.05
        bounds=([con_min,b*.5,d*.5,base_min],[con_max,b*1.5,d*1.5,base_max])
        adj,p0,bounds=check_fit_conditioning(p0,bounds,adjust='start')
        #### Control Fit Here: #####################################p0=[beta,Gamma,gamma,baseline]
        popt, pcov = curve_fit(g2_fit_func, x[xl[0]:sign_xl_max*xl[1]], y[xl[0]:sign_xl_max*xl[1]] , p0= p0,bounds=bounds)
        #########################################################################################
        perr = np.sqrt(np.diag(pcov))
        man_fit_result_dict[u][str(i)]['prelim_fit_params']={'beta':popt[0],'beta_err':perr[0],'Gamma':popt[1],'Gamma_err':perr[1],'gamma':popt[2],'gamma_err':perr[2],'base':popt[3],'base_err':perr[3]}
        r2=np.round(R_2(y,g2_fit_func(x, *popt)),4)
        if len(y)>10:
            R2_contrast=np.round(R_2(y[:10],g2_fit_func(x[:10], *popt)),4)
            R2_baseline=np.round(R_2(y[-10:],g2_fit_func(x[-10:], *popt)),4)
        else:
            R2_contrast=r2;R2_baseline=r2
        man_fit_result_dict[u][str(i)]['R2']={'R2':r2,'R2_contrast':R2_contrast,'R2_baseline':R2_baseline}
        man_fit_result_dict[u][str(i)]['outliers']=out_index
        plt.subplot(1,2,2)
        cp=plt.semilogx(x[xl[0]:sign_xl_max*xl[1]], y[xl[0]:sign_xl_max*xl[1]],'o',label='[%s] R$^2$=%s'%(i,r2))
        color=cp[0].get_color()
        plt.title('uid: '+u[:8]+' Q=%s $\AA^{-1}$'%q[:8])
        plt.semilogx(xplot,g2_fit_func(xplot, *popt),'-',color=color)
        plt.xlabel(r'$\tau$ [s]',fontsize=14);plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)',fontsize=14)
        ax=plt.gca()
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        ax.legend(fontsize=10,loc='lower left', bbox_to_anchor=(1., 0.0))
        plt.grid(b=True)
        plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=wspace, hspace=hspace)
    return man_fit_result_dict

def plot_fit_results(boundaries,raw_data,uid,phi_analysis,*argv, **kwargs):
    
    if 'plot_all' in kwargs:
        plot_all = kwargs['plot_all']
    else:
        plot_all=False
    
    if 'row_scale' in kwargs:
        row_scale = kwargs['row_scale']
    else:
        row_scale = 4
    if 'wspace' in kwargs:
        wspace=kwargs['wspace']
    else:
        wspace=1
    if 'hspace' in kwargs:
        hspace=kwargs['hspace']
    else:
        hspace=.5
    if 'tt_zero' in kwargs:
        tt_zero = kwargs['tt_zero']
        auto_tt_zero = False
    else:
        auto_tt_zero = True
    
    mak_list=['o','v','^','s','p','+','*','d','<','>']
    
    if phi_analysis:
        n_row=len(list(boundaries.keys()))
    else:
        n_row=int(np.ceil(len(list(boundaries.keys()))/2))
    fig,ax=plt.subplots(n_row,2,figsize=(12,n_row*row_scale))
    index_dict={}
    index=0
    plt_ct=1
    for qq,q in enumerate(list(boundaries.keys())):
        for pp,p in enumerate(list(boundaries[q].keys())):
            plt.subplot(n_row,2,plt_ct)
            mak_count=1
            for tt,t in enumerate(list(boundaries[q][p].keys())):
                index_dict[str(index)]={'Q':q,'Phi':p,'t_age':t}
                if boundaries[q][p][t]['bound_results']['status']=='complete':
                    mak=mak_list[int(np.ceil(mak_count/10))-1]
                    select=np.invert(boundaries[q][p][t]['bound_results']['outliers'])
                    x=raw_data[q][p][t]['x_dat'][select]
                    y=raw_data[q][p][t]['y_dat'][select]
                    if phi_analysis:
                        if auto_tt_zero:
                            t_age=float(t)-boundaries[q][p][t]['tt_zero']
                        else:
                             t_age=float(t)-tt_zero
                    else:
                        t_age=float(t)
                        print('careful, no time offset taken into account!')
                    cp=plt.semilogx(x,y,mak,label='[%s] %s $\pm$ %s'%(index,np.round(t_age,2),np.round(boundaries[q][p][t]['age_width']/2,2)))
                    color=cp[0].get_color()
                    try:
                        x_start=np.min(x);x_stop=np.max(x)
                    except:
                        print(q,p,t)
                    x_num=int((np.log10(x_stop)-np.log10(x_start))*10)
                    xplot=np.logspace(np.log10(x_start)-.5,np.log10(x_stop)+.5,x_num)
                    a=boundaries[q][p][t]['prelim_fit_params']['beta'];b=boundaries[q][p][t]['prelim_fit_params']['Gamma']
                    c=boundaries[q][p][t]['prelim_fit_params']['gamma'];d=boundaries[q][p][t]['prelim_fit_params']['base']
                    plt.semilogx(xplot,g2_fit_func(xplot,a,b,c,d),'-',color=color)
                else:
                    if plot_all:
                        mak=mak_list[int(np.ceil(mak_count/10))-1]
                        x=raw_data[q][p][t]['x_dat']
                        y=raw_data[q][p][t]['y_dat']
                        if phi_analysis:
                            if auto_tt_zero:
                                t_age=float(t)-boundaries[q][p][t]['tt_zero']
                            else:
                                 t_age=float(t)-tt_zero
                        else:
                            t_age=float(t)
                            print('careful, no time offset taken into account!')
                        cp=plt.semilogx(x,y,mak,fillstyle='none',label='[%s] %s $\pm$ %s'%(index,np.round(t_age,2),np.round(boundaries[q][p][t]['age_width']/2,2)))
                #print('[',index,']',q,p,t)
                index+=1
                mak_count+=1
            plt_ct+=1
            plt.title('uid: '+uid+'  Q = %s $\AA^{-1}$  $\Phi$=%s'%(np.round(float(q),4),p));plt.grid()
            ax=plt.gca()
            box = ax.get_position()
            ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
            #ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            ax.legend(title=r't$_{age}$ $\pm$ $\Delta$t$_{age}$ [s]',fontsize=8,loc='lower left', bbox_to_anchor=(1., 0.0))
            plt.xlabel(r'$\tau$ [s]',fontsize=12);plt.ylabel(r'g$_2$(t$_{age}$,$\tau$)',fontsize=12)
            plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=wspace, hspace=hspace)
            #plt.tight_layout()
    return index_dict         

def remove_data_from_boundaries(boundaries,index_dict,index_list):
    for i in index_list:
        q=index_dict[str(i)]['Q'];p=index_dict[str(i)]['Phi'];t=index_dict[str(i)]['t_age']
        boundaries[q][p][t]['bound_results']={'status' :'not_fitable'}
        boundaries[q][p][t]['prelim_fit_params']={}
        
def plot_fit_boundaries(boundaries,uid,phi_analysis,phi,*argv, **kwargs):
    
    if 'tt_zero' in kwargs:
        tt_zero = kwargs['tt_zero']
        auto_tt_zero = False
    else:
        auto_tt_zero = True
    
    # plot current status of fit boundaries:
    fig,ax=plt.subplots(1,2,figsize=(12,4))
    
    if not phi_analysis:
        phi=[-999]
        phi_nr=[0]
    else:
        pass
    
    for pp in phi:
        for qq in list(boundaries.keys()):
            try: # if data available for this phi and Q
                if pp==phi[0]:
                    if phi_analysis:
                        title_str='uid: '+uid+'   $\Phi$='+str(pp)+'$^o$'
                    else:
                        title_str='uid: '+uid
                    if len(title_str)>30:
                        title_str=title_str[:30]+'\n'+title_str[30:]
                    plt.subplot(1,2,1)
                    plt.title(title_str,fontsize=10)
                    #plt.title('uid: '+uid+'   $\Phi$='+str(pp)+'$^o$')
                    plt.xlabel('t$_{age}$ [s]',fontsize=12);plt.ylabel('Q [$\AA^{-1}$]',fontsize=12)
                    for t in list(boundaries[qq][str(pp)].keys()):
                        if boundaries[qq][str(pp)][t]['bound_results']['status']=='complete':
                            c_mak='go';
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='not_fitable':
                            c_mak='r+'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='masked':
                            c_mak='kd'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='incomplete' and boundaries[qq][str(pp)][t]['bound_results']['contrast']=='not_determined':
                            c_mak='cv'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='incomplete' and boundaries[qq][str(pp)][t]['bound_results']['baseline']=='not_determined':
                            c_mak='m^'
                        if phi_analysis:
                            if auto_tt_zero:
                                plt.plot(float(t)-boundaries[qq][str(pp)][t]['tt_zero'],float(qq),c_mak)
                            else:
                                plt.plot(float(t)-tt_zero,float(qq),c_mak)
                        else:
                            plt.plot(float(t),float(qq),c_mak)
                elif pp==phi[1]:
                    if phi_analysis:
                        title_str='uid: '+uid+'   $\Phi$='+str(pp)+'$^o$'
                    else:
                        itle_str='uid: '+uid
                    plt.subplot(1,2,2)
                    plt.title(title_str,fontsize=10)
                    #plt.title('uid: '+uid+'   $\Phi$='+str(pp)+'$^o$')
                    plt.xlabel('t$_{age}$ [s]',fontsize=12);plt.ylabel('Q [$\AA^{-1}$]',fontsize=12)
                    for t in list(boundaries[qq][str(pp)].keys()):
                        if boundaries[qq][str(pp)][t]['bound_results']['status']=='complete':
                            c_mak='go';
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='masked':
                            c_mak='kd'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='not_fitable':
                            c_mak='r+'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='incomplete' and boundaries[qq][str(pp)][t]['bound_results']['contrast']=='not_determined':
                            c_mak='cv'
                        elif boundaries[qq][str(pp)][t]['bound_results']['status']=='incomplete' and boundaries[qq][str(pp)][t]['bound_results']['baseline']=='not_determined':
                            c_mak='m^'
                        if phi_analysis:
                            if auto_tt_zero:
                                plt.plot(float(t)-boundaries[qq][str(pp)][t]['tt_zero'],float(qq),c_mak)
                            else:
                                plt.plot(float(t)-tt_zero,float(qq),c_mak)       
                        else:
                            plt.plot(float(t),float(qq),c_mak)

            except:
                print('No data available for Q='+qq+' Phi='+str(pp))
    x_lim=plt.xlim();y_lim=plt.ylim();
    plt.plot(-999,-999,'r+',label='not fitable');plt.plot(-999,-999,'go',label='fitting complete');plt.plot(-999,-999,'cv',label='fitting incomplete: \nbaseline only')
    plt.plot(-999,-999,'m^',label='fitting incomplete: \ncontrast only');plt.plot(-999,-999,'kd',label='masked')
    plt.xlim(x_lim);plt.ylim(y_lim)
    plt.legend(fontsize=12)
    ax=plt.gca()
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.tight_layout()
    
def boundaries_2_fit_result_dict(boundaries,md):
    fit_result_dict={}
    fit_result_dict['metadata']=md
    fit_result_dict['data']={}
    qs=list(boundaries.keys())
    for qq,q in enumerate(qs):
        fit_result_dict['data'][q]={}
        data_at_this_Q=False
        for pp,p in enumerate(list(boundaries[q].keys())):
            fit_result_dict['data'][q][p]={}
            Gam=[];Gam_err=[];gam=[];gam_err=[];beta=[];beta_err=[];base=[];base_err=[];ages=[];age_width=[]
            for tt,t in enumerate(list(boundaries[q][p].keys())):
                if boundaries[q][p][t]['bound_results']['status']=='complete':
                    data_at_this_Q=True
                    Gam+=[boundaries[q][p][t]['prelim_fit_params']['Gamma']];gam+=[boundaries[q][p][t]['prelim_fit_params']['gamma']]
                    Gam_err+=[boundaries[q][p][t]['prelim_fit_params']['Gamma_err']];gam_err+=[boundaries[q][p][t]['prelim_fit_params']['gamma_err']]
                    base+=[boundaries[q][p][t]['prelim_fit_params']['base']];base_err+=[boundaries[q][p][t]['prelim_fit_params']['base_err']]
                    beta+=[boundaries[q][p][t]['prelim_fit_params']['beta']];beta_err+=[boundaries[q][p][t]['prelim_fit_params']['beta_err']]
                    ages+=[float(t)];age_width+=[boundaries[q][p][t]['age_width']]
            fit_result_dict['data'][q][p]={'Gam':Gam,'Gam_err':Gam_err,'gam':gam,'gam_err':gam_err,'beta':beta,'beta_err':beta_err,'base':base,'base_err':base_err,'ages':ages,'age_width':age_width}
        if not data_at_this_Q:   # if no fitted data exist at all for this Q, remove this Q from the dictionary
            trash=fit_result_dict['data'].pop(q)    
    return fit_result_dict

def find_most_neighbours(neighbours):
    next_fit={}
    phis=list(neighbours.keys())
    next_fit={}
    #Qs=list(neighbours[phis].keys())
    for pp,p in enumerate(phis):
        next_fit[p]={}
        phi_max=0
        for qq,q in enumerate(list(neighbours[p].keys())):
            for tt,t in enumerate(list(neighbours[p][q].keys())):
                if neighbours[p][q][t]['nr_neighbours']>phi_max:
                    phi_max=neighbours[p][q][t]['nr_neighbours']
                    next_fit[p]={'Q':q,'t_age':t,'nr_neighbours':phi_max,'baseline':neighbours[p][q][t]['baseline'],'contrast':neighbours[p][q][t]['contrast']}
    return next_fit

def complete_neighbours(boundaries, *argv, **kwargs):
    """
    Function finds datasets [Q,Phi,age] with 'incomplete' fits, determines number of neighbours with complete fits and what are their values for contrast and baseline
    returns dictionary neighbours[Q][Phi][t_age]={'nr_neighbours','n_base','n_con'}
    option argument: include_Phi=True/False -> if True include data for other Phi value in enighbour search 
    """
    if 'include_Phi' in kwargs:
        include_Phi = kwargs['include_Phi']
    else:
        include_Phi = False
    
    phis=list(boundaries[list(boundaries.keys())[0]].keys())
    Qs=list(boundaries.keys())
    #print(Qs[-1])
    t_ages=list(boundaries[Qs[0]][phis[0]].keys())
    #print(len(t_ages))
    neighbours={}
    for pp,p in enumerate(phis):
        neighbours[str(p)]={}
        #incomplete_ct=0
        for qq,q in enumerate(Qs):
            #neighbours[str(p)][q]={}
            for tt,t in enumerate(list(boundaries[q][p].keys())):
                if boundaries[q][p][t]['bound_results']['status'] == 'incomplete':
                    try:
                        neighbours[str(p)][q][t]={}
                    except:
                        neighbours[str(p)][q]={}
                        neighbours[str(p)][q][t]={}
                    cn_ct=0
                    base=[];con=[] 
                    try: # same age, Q-1
                        if qq-1>=0 and boundaries[Qs[qq-1]][p][t]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq-1]][p][t]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq-1]][p][t]['bound_results']['contrast'])
                    except:
                        pass
                    try: # same age, Q+1
                        if qq+1 <= len(Qs) and boundaries[Qs[qq+1]][p][t]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq+1]][p][t]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq+1]][p][t]['bound_results']['contrast'])
                    except:
                        pass
                    try: # Q-1, age-1
                        if qq-1>=0 and tt-1 >=0 and boundaries[Qs[qq-1]][p][t_ages[tt-1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq-1]][p][t_ages[tt-1]]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq-1]][p][t_ages[tt-1]]['bound_results']['contrast'])
                    except:
                        pass
                    try: # Q-1, age+1
                        if qq-1>=0 and tt+1 <=len(t_ages) and boundaries[Qs[qq-1]][p][t_ages[tt+1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq-1]][p][t_ages[tt+1]]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq-1]][p][t_ages[tt+1]]['bound_results']['contrast'])
                    except:
                        pass
                    try: # same Q, age-1
                        if tt-1 >=0 and boundaries[q][p][t_ages[tt-1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[q][p][t_ages[tt-1]]['bound_results']['baseline'])
                            con.append(boundaries[q][p][t_ages[tt-1]]['bound_results']['contrast'])
                    except:
                        pass
                    try: # same Q, age+1
                        if tt+1 <= len(t_ages) and boundaries[q][p][t_ages[tt+1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[q][p][t_ages[tt+1]]['bound_results']['baseline'])
                            con.append(boundaries[q][p][t_ages[tt+1]]['bound_results']['contrast'])
                    except:
                        pass
                    try: #  Q+1, age-1
                        if qq+1 <= len(Qs) and tt-1 >=0 and boundaries[Qs[qq+1]][p][t_ages[tt-1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq+1]][p][t_ages[tt-1]]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq+1]][p][t_ages[tt-1]]['bound_results']['contrast'])
                    except:
                        pass
                    try: #  Q+1, age+1
                        if qq+1 <= len(Qs) and tt+1 <= len(t_ages) and boundaries[Qs[qq+1]][p][t_ages[tt+1]]['bound_results']['status']== 'complete':
                            cn_ct=cn_ct+1
                            #print(q,p,t)
                            base.append(boundaries[Qs[qq+1]][p][t_ages[tt+1]]['bound_results']['baseline'])
                            con.append(boundaries[Qs[qq+1]][p][t_ages[tt+1]]['bound_results']['contrast'])
                    except:
                        pass
                    
                    if include_Phi:
                        temp_phi=deepcopy(phis)
                        temp_phi.remove(p)
                        try: # other Phi, same age, same Q
                            if boundaries[Qs[qq]][temp_phi[0]][t]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq]][temp_phi[0]][t]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq]][temp_phi[0]][t]['bound_results']['contrast'])
                        except:
                            pass
                        try: # other Phi, same age, Q-1
                            if qq-1>=0 and boundaries[Qs[qq-1]][temp_phi[0]][t]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq-1]][temp_phi[0]][t]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq-1]][temp_phi[0]][t]['bound_results']['contrast'])
                        except:
                            pass
                        try: # other Phi, same age, Q+1
                            if qq+1 <= len(Qs) and boundaries[Qs[qq+1]][temp_phi[0]][t]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq+1]][temp_phi[0]][t]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq+1]][temp_phi[0]][t]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,  Q-1, age-1
                            if qq-1>=0 and tt-1 >=0 and boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,  Q-1, age+1
                            if qq-1>=0 and tt+1 <=len(t_ages) and boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq-1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,  same Q, age-1
                            if tt-1 >=0 and boundaries[q][temp_phi[0]][t_ages[tt-1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[q][temp_phi[0]][t_ages[tt-1]]['bound_results']['baseline'])
                                con.append(boundaries[q][temp_phi[0]][t_ages[tt-1]]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,  same Q, age+1
                            if tt+1 <= len(t_ages) and boundaries[q][temp_phi[0]][t_ages[tt+1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[q][temp_phi[0]][t_ages[tt+1]]['bound_results']['baseline'])
                                con.append(boundaries[q][temp_phi[0]][t_ages[tt+1]]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,   Q+1, age-1
                            if qq+1 <= len(Qs) and tt-1 >=0 and boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt-1]]['bound_results']['contrast'])
                        except:
                            pass
                        try: #other Phi,   Q+1, age+1
                            if qq+1 <= len(Qs) and tt+1 <= len(t_ages) and boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['status']== 'complete':
                                cn_ct=cn_ct+1
                                #print(q,p,t)
                                base.append(boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['baseline'])
                                con.append(boundaries[Qs[qq+1]][temp_phi[0]][t_ages[tt+1]]['bound_results']['contrast'])
                        except:
                            pass
                    
                    neighbours[str(p)][q][t]={'nr_neighbours':cn_ct,'baseline':base,'contrast':con}
    return neighbours

def incomplete_cts(boundaries,set_not_fitable=False,verbose=False, *argv, **kwargs):
    if 'marker_str' in kwargs:
        marker_str = kwargs['marker_str']
    else:
        marker_str = 'not_fitable'
    incomplete_counts={}
    phis=list(boundaries[list(boundaries.keys())[0]].keys())
    for p in phis:
        incomplete_ct=0
        for q in list(boundaries.keys()):
            for t in list(boundaries[q][p].keys()):
                if boundaries[q][p][t]['bound_results']['status'] == 'incomplete':
                    incomplete_ct=incomplete_ct+1
                    if set_not_fitable:
                        if verbose:
                            print('going to replace incomplete by '+marker_str+'!')
                        boundaries[q][p][t]['bound_results']['status']=marker_str
                        if marker_str == 'not_fitable':
                            boundaries[q][p][t]['prelim_fit_params']={}
                            boundaries[q][p][t]['bound_results']={'status' :marker_str}
        incomplete_counts[p]=incomplete_ct
        if verbose:
            print('total number of incomplete fits for Phi=%s : '%p,incomplete_ct)
    return incomplete_counts

def unmask_fit_results(boundaries):
    for u in list(boundaries.keys()):
        phis=list(boundaries[u][list(boundaries[u].keys())[0]].keys())
        for p in phis:
            for q in list(boundaries[u].keys()):
                for t in list(boundaries[u][q][p].keys()):
                    if boundaries[u][q][p][t]['bound_results']['status'] == 'masked':
                        boundaries[u][q][p][t]['bound_results']['status']=boundaries[u][q][p][t]['bound_results']['ini_status']
    return boundaries

def load_hdf_data(uid_list,data_dir, *argv, **kwargs):
    """
    function to load hdf file with calculated correlation functions, etc.
    default filenames: 'uid=%s_phi_4x_20deg_Res.h5' AND 'uid=%s_rings_Res.h5'
    change with optional arguments 'filename1' and 'filename2'
    takes optional arguments for extract_xpcs_results_from_h5: onekey=None, exclude_keys=None, two_time_qindex=None
    """
    if 'filename1' in kwargs:
        filename1 = kwargs['filename1']
    else:
        filename1 = 'uid=%s_phi_4x_20deg_Res.h5'
    if 'filename2' in kwargs:
        filename2 = kwargs['filename2']
    else: 
        filename2 = 'uid=%s_rings_Res.h5'
    if 'onekey' in kwarg:
        onekey = kwargs['onekey']
    else:
        onekey = None
    if 'exclude_keys' in kwargs:
        exclude_keys = kwargs['exclude_keys']
    else:
        exclude_keys = None
    if 'two_time_qindex' in kwargs:
        two_time_qindex = kwargs['two_time_qindex']
    else:
        two_time_qindex = None
        
    total_res = {}

    for k in uid_list:
        uid = k
        print('loading data for uid: ',uid)
        uid_full =  get_meta_data( uid )['uid']
        try:
            inDir =  data_dir + uid + '/'   #legacy: previously used 'short' uid for directory name...
            if phi_analysis:
                print('trying to load: ',inDir+filename1%uid_full)
                #input_filename='uid=%s_phi_4x_20deg_Res.h5'%uid_full
                total_res[uid] = extract_xpcs_results_from_h5( filename = filename1%uid_full, import_dir = inDir , onekey=onekey,exclude_keys=exclude_keys,two_time_qindex=two_time_qindex)
            else:
                print('trying to load: ',inDir+filename2%uid_full)
                #input_filename='uid=%s_Res.h5'%uid_full
                total_res[uid] = extract_xpcs_results_from_h5( filename = filename2%uid_full, import_dir = inDir , onekey=onekey,exclude_keys=exclude_keys,two_time_qindex=two_time_qindex)
        except:
            inDir =  data_dir + uid_full + '/'   
            if phi_analysis:
                print('trying to load: ',inDir+filename1%uid_full)
                #input_filename='uid=%s_phi_4x_20deg_Res.h5'%uid_full
                total_res[uid] = extract_xpcs_results_from_h5( filename = filename1%uid_full, import_dir = inDir , onekey=onekey,exclude_keys=exclude_keys,two_time_qindex=two_time_qindex)
            else:
                print('trying to load: ',inDir+filename2%uid_full)
                #input_filename='uid=%s_Res.h5'%uid_full
                total_res[uid] = extract_xpcs_results_from_h5( filename = filename1%uid_full, import_dir = inDir , onekey=onekey,exclude_keys=exclude_keys,two_time_qindex=two_time_qindex)

    print('available dictionary keys in imported data: ', total_res[uid].keys()   )
    return total_res


def pad_length(arr,pad_val=np.nan):
    """
    arr: 2D matrix
    pad_val: values being padded
    adds pad_val to each row, to make the length of each row equal to the lenght of the longest row of the original matrix
    -> used to convert python generic data object to HDF5 native format
    function fixes python bug in padding (np.pad) integer array with np.nan
    update June 2023: remove use of np.shape and np.size that doesn't work (anymore?) on arrays with inhomogenous size
    by LW 12/30/2017
    """
    max_len=[]
    for i in range(len(arr)):
        max_len.append([len(arr[i])])
    max_len=np.max(max_len)
    for l in range(len(arr)):
        arr[l]=np.pad(arr[l]*1.,(0,max_len-np.size(arr[l])),mode='constant',constant_values=pad_val)
    return arr
    
def get_md_by_age(metadata_dict,tage):
    """
    function used to return metadata for time-stitched SAXS data based on timestamp
    get_md_by_age(metadata_dict,tage)
    metadata_dict: time-stitched metadata dictionary; keys are tuples (first_time,last_time)
    tage: time for which we're looking for corresponding metadat
    returns: metadat_dict entry for key with (tage>=first_time & tage<=last_time)
    by LW 10/02/2023
    """
    key=False
    for i in list(metadata_dict.keys()):
        if tage >= i[0] and tage <= i[1]:
            key=i
    if not key:
        raise Exception('ERROR: could not find metadate for age %ss'%tage)
    else: return metadata_dict[key]