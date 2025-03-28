from copy import deepcopy
import pandas as pd
from matplotlib import pyplot as plt
from fpdf import FPDF
import time
from pyOlog import *


def make_mixmd_table(md,path='',plot=True):
    """
    mixed metadata from WAXS / cSAXS: printing information is in XPCS dataset, WAXS parameters in WAXS dataset -> in analysis we merge the two
    remove unnesessary metadata and metadata referring to the XPCS dataset
    """
    min_dict = deepcopy(md)
    for k in list(min_dict):
        if k[-1]=='_':
            del min_dict[k]
    for k in ['uid', 'time', 'scan_id', 'auto_pipeline', 'user_group','beamline_id', 'owner', 'OAV_resolution [um_pixel]', 'plan_type','plan_name', 'XPCS_data', 'exposure time', 'acquire period','shutter mode', 'number of images', 'data path', 
              'sequence id','T_yoke', 'T_sample', 'T_sample_stinger', 'analysis', 'feedback_x','feedback_y', 'detectors','beam_position_dict','Measurement']:
        try:
            del min_dict[k]
        except:
            pass
    df=pd.DataFrame.from_dict(min_dict,orient='index')
    fig, ax =plt.subplots(figsize=(14,2))
    ax.axis('tight')
    ax.axis('off')
    the_table = ax.table(cellText=df.values,rowLabels=list(min_dict.keys()),cellLoc='center',fontsize=16)
    ax.set_title('uid: %s  scan_id: %s'%(min_dict['pil800k_uid'],min_dict['pil800k_scan_id']),y=.15)
    fn=path+'md_figure.png'
    plt.savefig(fn,format='png',dpi=150, bbox_inches='tight')
    if not plot:
        plt.close(fig)
    return fn


def capture_calibration(aintegrator,cfilepath,path='',plot=False):
    """
    Specific macro for WAXS analysis: captures details of geometry calibration (via pyFAI) as an image for pdf report
    """
    aintegrator_str_=str(aintegrator)
    aintegrator_str=aintegrator_str_.replace('\t','')
    fig,ax = plt.subplots(figsize=(10,1))
    plt.axis('off')
    plt.text(0,0,aintegrator_str)
    plt.title('Loading detector calibration from file: %s'%cfilepath)
    fn=path+'calibration.png'
    plt.savefig(fn,format='png',dpi=150, bbox_inches='tight')
    if not plot:
        plt.close(fig)
    return fn

def WAXS_ANALYSIS_PDF_REPORT(res_dir, pdf_filename, pdf_dict, save_dict, sfn):
    """
    first version, included full pattern fits, which have now been moved to post-processing
    res_dir: directory for saving the pdf report
    pdf_filename: filename of pdf report
    save_dict: dictionary with entries and image locations for pdf report
    sfn: directory/filename where the analysis/processing results corresponding to this pdf have been saved (usually as .pkl)
    """
    class PDF(FPDF):
        def header(self):
            # Logo
            self.image('/nsls2/data/chx/legacy/analysis/2018_3/lwiegart/development'+'/test_logo.png', 10, 8, 50)
            self.set_font('helvetica', 'B', .1)
            # Move to the right
            self.cell(55)
            # Title
            t = time.localtime()
            current_time = time.strftime("%D %H:%M:%S", t)
            self.set_font('helvetica', 'B', 6)
            self.multi_cell(140, 3, 'WAXS analysis report    uid: %s \nworking directory: %s               \ncreated: %s'%(save_dict['meta_data']['pil800k_uid'],res_dir,current_time), 1,  'C')
            # Line break
            self.ln(8)

        # Page footer
        def footer(self):
            # Position at 1.5 cm from bottom
            self.set_y(-15)
            # Arial italic 8
            self.set_font('helvetica', 'I', 8)
            # Page number
            #self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0,0, 'C')

    def check_page_break(pdf,min_margin,verbose=False):
        y=pdf.get_y()
        if verbose:
            print('current position: %s  required space: %s -> %s'%(y,min_margin,y+min_margin))
        if (y+min_margin) >279: # this is for the current page layout with page number as footer, Letter size and standard margins
            return pdf.add_page()

    def hyper_write(pdf,string,font='',fontsize=12,style='',color=[0,0,0]):
        pdf.set_font('', style, fontsize)
        pdf.set_text_color(color[0],color[1],color[2])
        pdf.write(0,string)
        pdf.set_text_color(0,0,0)

    text_color_dict={'fail':[255,0,0],'pass':[0,255,0],'warning':[255,165,0]}

    pdf = PDF('P', 'mm', 'Letter')
    pdf.set_auto_page_break(False)
    pdf.alias_nb_pages()
    pdf.compress = False
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 14)  
    pdf.cell(80, 10, 'Automated WAXS data Processing and Analysis')
    pdf.set_font('helvetica','B', 12)
    pdf.ln()

    ### metadata table
    pdf.write(5, 'Dataset:');pdf.ln()
    pdf.image(pdf_dict['dataset'],x=10,w=180)
    check_page_break(pdf,20)
    pdf.image(pdf_dict['calibration'],w=180)

    ### intensity trace
    check_page_break(pdf,70)
    pdf.ln();pdf.write(5, 'Intensity Trace');pdf.ln(12)#;pdf.ln(8)
    pdf.image(pdf_dict['intensity trace'],h=60)
    ### IF in-situ dataset: 3 images of filament crossing X-ray beam and 3 images printhead shadow
    if '2D_images_filament_crossing_beam' in pdf_dict.keys():
        check_page_break(pdf,70)
        pdf.ln();pdf.write(5, 'filament crossing X-ray beam');pdf.ln()#;pdf.ln(8)
        pdf.image(pdf_dict['2D_images_filament_crossing_beam'],h=50)
    if '2D_images_end_of_shadow' in pdf_dict.keys():
        check_page_break(pdf,70)
        pdf.ln();pdf.write(5, 'printhead shadow');pdf.ln()#;pdf.ln(8)
        pdf.image(pdf_dict['2D_images_end_of_shadow'],h=50)

    ### Detector Masks
    check_page_break(pdf,70)
    pdf.ln();pdf.write(5, 'Detector Masks');pdf.ln()#;pdf.ln(8)
    pdf.image(pdf_dict['2D_images_mask'],x=-15,h=50)

    ### Crystallization Onset
    check_page_break(pdf,60)
    pdf.ln();pdf.write(5, 'Crystallization Onset');pdf.ln()#;pdf.ln(8)
    pdf.image(pdf_dict['crystallization_onset'],h=50)
    pdf.set_font('helvetica', 'B', 8)
    pdf.write(0,'Our best guess for onset  of crystallization occuring withing this dataset: ')
    if save_dict['crystallization_onset']['in_situ_crystallization']:
        cc='pass'
    else: cc='fail'
    hyper_write(pdf,string=str(save_dict['crystallization_onset']['in_situ_crystallization']),font='',fontsize=8,style='',color=text_color_dict[cc]);pdf.set_font('helvetica','B', 12);pdf.ln(12)

    ### check for all images with crystal phase and plot selected I(Q)
    check_page_break(pdf,60)
    if 'all_crystalline' in pdf_dict.keys():
        pdf.write(text='Checking if sample is crystalline throughout the dataset');pdf.ln(12)
        y=pdf.get_y();x=90
        pdf.image(pdf_dict['all_crystalline'],h=50)
    else: x=None;y=None;pdf.write(text='Time-resolved I(Q)');pdf.ln(6)
    pdf.image(pdf_dict['timeseries_I_Q'],x=x,y=y,h=50);pdf.ln()
    if 'all_crystalline' in pdf_dict.keys():
        pdf.set_font('helvetica', 'B', 8)
        pdf.write(0,'Our best guess for the material being crystalline throughout the whole dataset: ')
        if save_dict['all_crystalline_dict']['all_crystalline']:
            cc='pass'
        else: cc='fail'
        hyper_write(pdf,string=str(save_dict['all_crystalline_dict']['all_crystalline']),font='',fontsize=8,style='',color=text_color_dict[cc]);pdf.set_font('helvetica','B', 12);pdf.ln(12)

    ### FITs
    if 'fit_examples_I_Q' in pdf_dict.keys():
        check_page_break(pdf,180);pdf.write(text='Fits of I(Q)');pdf.ln()
        pdf.image(pdf_dict['fit_examples_I_Q'],w=160)
        check_page_break(pdf,240);pdf.write(text='Fit Parameters');pdf.ln()
        pdf.image(pdf_dict['I_Q_fit_parameters'],h=230)

    ### Azimuthal Dependence
    check_page_break(pdf,70);pdf.write(text='Azimuthal Dependence');pdf.ln(12)
    y=pdf.get_y()
    pdf.image(pdf_dict['2D_image_averaged_end_of_series'],h=50)
    pdf.image(pdf_dict['phi_map_averaged_end_of_series'],x=60,y=y,h=50)
    pdf.image(pdf_dict['phi_cuts_averaged_end_of_series'],x=120,y=y,h=50);pdf.ln(12)
    pdf.set_font('helvetica', 'B', 8)
    if sfn:
        pdf.write(0,'Data from this analysis has been saved as:\n%s'%sfn)
    else:
        pdf.write(0,'Data from this analysis has NOT been saved.')

    pdf.output(res_dir+'%s'%(pdf_filename))


def WAXS_ANALYSIS_PDF_REPORT_v2(res_dir, pdf_filename, pdf_dict, save_dict, sfn):
    """
    _v2: removed full pattern fits, just looking for crystallization onset and phase behavior
    res_dir: directory for saving the pdf report
    pdf_filename: filename of pdf report
    save_dict: dictionary with entries and image locations for pdf report
    sfn: directory/filename where the analysis/processing results corresponding to this pdf have been saved (usually as .pkl)
    """
    class PDF(FPDF):
        def header(self):
            # Logo
            self.image('/nsls2/data/chx/legacy/analysis/2018_3/lwiegart/development'+'/test_logo.png', 10, 8, 50)
            self.set_font('helvetica', 'B', .1)
            # Move to the right
            self.cell(55)
            # Title
            t = time.localtime()
            current_time = time.strftime("%D %H:%M:%S", t)
            self.set_font('helvetica', 'B', 6)
            self.multi_cell(140, 3, 'WAXS analysis report    uid: %s \nworking directory: %s               \ncreated: %s'%(save_dict['meta_data']['pil800k_uid'],res_dir,current_time), 1,  'C')
            # Line break
            self.ln(8)

        # Page footer
        def footer(self):
            # Position at 1.5 cm from bottom
            self.set_y(-15)
            # Arial italic 8
            self.set_font('helvetica', 'I', 8)
            # Page number
            #self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0,0, 'C')

    def check_page_break(pdf,min_margin,verbose=False):
        y=pdf.get_y()
        if verbose:
            print('current position: %s  required space: %s -> %s'%(y,min_margin,y+min_margin))
        if (y+min_margin) >279: # this is for the current page layout with page number as footer, Letter size and standard margins
            return pdf.add_page()

    def hyper_write(pdf,string,font='',fontsize=12,style='',color=[0,0,0]):
        pdf.set_font('', style, fontsize)
        pdf.set_text_color(color[0],color[1],color[2])
        pdf.write(0,string)
        pdf.set_text_color(0,0,0)

    text_color_dict={'fail':[255,0,0],'pass':[0,255,0],'warning':[255,165,0]}

    pdf = PDF('P', 'mm', 'Letter')
    pdf.set_auto_page_break(False)
    pdf.alias_nb_pages()
    pdf.compress = False
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 14)  
    pdf.cell(80, 10, 'Automated WAXS data Processing and Analysis')
    pdf.set_font('helvetica','B', 12)
    pdf.ln()

    ### metadata table
    pdf.write(5, 'Dataset:');pdf.ln()
    pdf.image(pdf_dict['dataset'],x=10,w=180)
    check_page_break(pdf,20)
    pdf.image(pdf_dict['calibration'],w=180)

    ### intensity trace
    check_page_break(pdf,70)
    pdf.ln();pdf.write(5, 'Intensity Trace');pdf.ln(12)#;pdf.ln(8)
    pdf.image(pdf_dict['intensity trace'],h=60)
    ### IF in-situ dataset: 3 images of filament crossing X-ray beam and 3 images printhead shadow
    if '2D_images_filament_crossing_beam' in pdf_dict.keys():
        check_page_break(pdf,70)
        pdf.ln();pdf.write(5, 'filament crossing X-ray beam');pdf.ln()#;pdf.ln(8)
        pdf.image(pdf_dict['2D_images_filament_crossing_beam'],h=50)
    if '2D_images_end_of_shadow' in pdf_dict.keys():
        check_page_break(pdf,70)
        pdf.ln();pdf.write(5, 'printhead shadow');pdf.ln()#;pdf.ln(8)
        pdf.image(pdf_dict['2D_images_end_of_shadow'],h=50)

    ### Detector Masks
    check_page_break(pdf,70)
    pdf.ln();pdf.write(5, 'Detector Masks');pdf.ln()#;pdf.ln(8)
    pdf.image(pdf_dict['2D_images_mask'],x=-15,h=50)

    ### Crystallization Onset
    check_page_break(pdf,60)
    pdf.ln();pdf.write(5, 'Crystallization Onset');pdf.ln()#;pdf.ln(8)
    pdf.image(pdf_dict['search crystallization_onset'],h=50)
    pdf.set_font('helvetica', 'B', 8)
    pdf.write(0,'Our best guess for classifying crystallization in this dataset: ')
    if save_dict['structure']['peaks']['crystallization_onset']:
        cc='pass'
        classification = 'in-situ crystallization'       
    else: 
        cc='fail'
        classification = save_dict['structure']['peaks']['crystallization_onset']['classification']
    hyper_write(pdf,string=classification,font='',fontsize=8,style='',color=text_color_dict[cc]);pdf.set_font('helvetica','B', 12);pdf.ln(12)

    ### Phase Behavior
    check_page_break(pdf,60)
    pdf.ln();pdf.write(5, 'Phase Behavior');pdf.ln()#;pdf.ln(8)
    pdf.image(pdf_dict['search beta_phase'],h=50)
    pdf.set_font('helvetica', 'B', 8)
    pdf.write(0,'Our best guess for classifying crystallization in this dataset: ')
    if save_dict['structure']['peaks']['crystallization_onset']:
        cc='pass'
        classification = 'in-situ crystallization into beta-phase'       
    else: 
        cc='fail'
        classification = save_dict['structure']['peaks']['crystallization_onset']['classification']
    hyper_write(pdf,string=classification,font='',fontsize=8,style='',color=text_color_dict[cc]);pdf.set_font('helvetica','B', 12);pdf.ln(12)

    ### Azimuthal Dependence
    check_page_break(pdf,70);pdf.write(text='Azimuthal Dependence');pdf.ln(12)
    y=pdf.get_y()
    pdf.image(pdf_dict['2D_image_averaged_end_of_series'],h=50)
    pdf.image(pdf_dict['phi_map_averaged_end_of_series'],x=60,y=y,h=50)
    pdf.image(pdf_dict['phi_cuts_averaged_end_of_series'],x=120,y=y,h=50);pdf.ln(12)
    pdf.set_font('helvetica', 'B', 8)
    if sfn:
        pdf.write(0,'Data from this analysis has been saved as:\n%s'%sfn)
    else:
        pdf.write(0,'Data from this analysis has NOT been saved.')

    pdf.output(res_dir+'%s'%(pdf_filename))



def WAXS_PATTERNFIT_PDF_REPORT(res_dir, pdf_filename, pdf_dict, save_dict):
    """
    for WAXS post analysis, mainly containing whole pattern fits and degree of crystallization
    res_dir: directory for saving the pdf report
    pdf_filename: filename of pdf report
    save_dict: dictionary with entries and image locations for pdf report
    sfn: directory/filename where the analysis/processing results corresponding to this pdf have been saved (usually as .pkl)
    """
    class PDF(FPDF):
        def header(self):
            # Logo
            self.image('/nsls2/data/chx/legacy/analysis/2018_3/lwiegart/development'+'/test_logo.png', 10, 8, 50)
            self.set_font('helvetica', 'B', .1)
            # Move to the right
            self.cell(55)
            # Title
            t = time.localtime()
            current_time = time.strftime("%D %H:%M:%S", t)
            self.set_font('helvetica', 'B', 6)
            self.multi_cell(140, 3, 'WAXS analysis report    uid: %s \nworking directory: %s               \ncreated: %s'%(save_dict['uid'],res_dir,current_time), 1,  'C')
            # Line break
            self.ln(8)

        # Page footer
        def footer(self):
            # Position at 1.5 cm from bottom
            self.set_y(-15)
            # Arial italic 8
            self.set_font('helvetica', 'I', 8)
            # Page number
            #self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')
            self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0,0, 'C')

    def check_page_break(pdf,min_margin,verbose=False):
        y=pdf.get_y()
        if verbose:
            print('current position: %s  required space: %s -> %s'%(y,min_margin,y+min_margin))
        if (y+min_margin) >279: # this is for the current page layout with page number as footer, Letter size and standard margins
            return pdf.add_page()

    def hyper_write(pdf,string,font='',fontsize=12,style='',color=[0,0,0]):
        pdf.set_font('', style, fontsize)
        pdf.set_text_color(color[0],color[1],color[2])
        pdf.write(0,string)
        pdf.set_text_color(0,0,0)

    text_color_dict={'fail':[255,0,0],'pass':[0,255,0],'warning':[255,165,0]}

    pdf = PDF('P', 'mm', 'Letter')
    pdf.set_auto_page_break(False)
    pdf.alias_nb_pages()
    pdf.compress = False
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 14)  
    pdf.cell(80, 10, 'WAXS full Pattern Fit and Analysis')
    pdf.set_font('helvetica','B', 12)
    pdf.ln()

# ['dataset', 'waxs_backgrounds', 'shadow_background_transmission',
#        'background_transmission', 'pattern_fits',
#        'crystallinity_computing_time', 'non_crystalline_params',
#        'more_crystalline_onset']    
    ### metadata table
    pdf.write(5, 'Dataset:');pdf.ln()
    pdf.image(pdf_dict['dataset'],x=10,w=180)
    pdf.ln()
    check_page_break(pdf,40)

    ### waxs_backgrounds
    pdf.write(5, 'Backgrounds for WAXS pattern fits:');pdf.ln()
    pdf.image(pdf_dict['waxs_backgrounds'],x=10,w=180)
    pdf.ln()
    check_page_break(pdf,80)

    ### 'waxs_backgrounds'
    if 'shadow_background_transmission' in pdf_dict.keys():
        pdf.write(5, 'Background with printhead shadow:');pdf.ln()
        pdf.image(pdf_dict['shadow_background_transmission'],x=10,w=180)
        pdf.ln()
        check_page_break(pdf,80)

    pdf.write(5, 'Background without printhead shadow:');pdf.ln()
    pdf.image(pdf_dict['background_transmission'],x=10,w=180)
    pdf.ln()
    check_page_break(pdf,60)

    ### 'pattern_fits'
    pdf.write(5, 'WAXS pattern fits:');pdf.ln()
    pdf.image(pdf_dict['pattern_fits'],x=10,w=170)
    pdf.ln()
    check_page_break(pdf,150)

    ### 'crystallinity_computing_time'
    pdf.write(5, 'Crystallinity and Computing time:');pdf.ln()
    pdf.image(pdf_dict['crystallinity_computing_time'],x=10,w=130)
    pdf.ln()
    check_page_break(pdf,60)

    ### 'x_waxs_map'
    pdf.write(5, 'Crystallinity map:');pdf.ln()
    pdf.image(pdf_dict['x_waxs_map'],x=20,w=120)
    pdf.ln()
    check_page_break(pdf,10)

    ### 'non_crystalline_params''
    pdf.write(5, 'Fit parameters of non-crystalline part:');pdf.ln()
    pdf.image(pdf_dict['non_crystalline_params'],x=10,w=130)
    pdf.ln()
    check_page_break(pdf,60)

    ### 'more_crystalline_onset'
    pdf.write(5, 'More diagnostics on crystallization onset:');pdf.ln()
    pdf.image(pdf_dict['more_crystalline_onset'],x=10,w=130);pdf.ln(12)
    pdf.set_font('helvetica', 'B', 8)
    pdf.write(0,'Data from this analysis has been saved as:\n%s'%save_dict['filename'])
        
    pdf.output(pdf_filename)


####### attach PDF report to Olog entry ################
def update_olog_with_analysisreport(shortuid, filename):
    client = OlogClient()
    searchstring='*'+shortuid+'*'
    logentry=client.find(search=searchstring)[0]
    logid  = logentry.id
    atch = [Attachment(open(filename,'rb'))]
    logentry.attachments=atch
    client.updateLog(logid,logentry)