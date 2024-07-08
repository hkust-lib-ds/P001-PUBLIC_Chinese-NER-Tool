import streamlit as st
from annotated_text import annotated_text
from ckip_transformers.nlp import CkipNerChunker
import itertools
from PIL import Image
import os
import zipfile
import pandas as pd
from io import StringIO
import plotly.express as px
import plotly.graph_objects as go
import re
import collections
import base64
import numpy as np
from streamlit_extras.stylable_container import stylable_container

ner_driver = CkipNerChunker(model="bert-base")

###############################################################
# set page config
###############################################################
#parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#hkust_favicon = Image.open(parent_dir + "/favicon.ico")
st.set_page_config(
    page_title="Chinese NER Tool 中文自動標注實體實例平台",
    page_icon='favicon.ico',
)

st.markdown("""
<style>
div[data-testid="stFileUploaderDeleteBtn"] {
  display: none;
  }
::-webkit-scrollbar {
    -webkit-appearance: none;
    width: 10px;
    }
::-webkit-scrollbar-thumb {
    border-radius: 5px;
    background-color: rgba(220, 220, 220, .5);
    -webkit-box-shadow: 0 0 1px rgba(255,255,255,.5);
    }
</style>
""", unsafe_allow_html=True)


#########################################################################################################################################
#########################################################################################################################################
# variables

###############################################################
# global variables
###############################################################
# "" for undefined
CKIP_ALL_NER_TAG = {"CARDINAL": "數字", "DATE":"日期", "EVENT": "事件", "FAC": "設施", "GPE": "行政區", 
                    "LANGUAGE": "語言", "LAW": "法律", "LOC": "地理區", "MONEY": "金錢", "NORP": "民族、宗教、政治團體", 
                    "ORDINAL": "序數", "ORG": "組織", "PERCENT": "百分比率", "PERSON": "人物", "PRODUCT": "產品", 
                    "QUANTITY": "數量", "TIME": "時間", "WORK_OF_ART": "作品", "": "未定義|UNDEFINED"}

CKIP_ALL_NER_TAG_COLORS = {
    "CARDINAL": "#FFBEBE", 
    "DATE": "#EEEFBF",
    "EVENT": "#EEC6ED",
    "FAC": "#D199B0", 
    "GPE": "#FFBEFF",
    "LANGUAGE": "#BEFFFF", 
    "LAW": "#FFDDBE", 
    "LOC": "#99BCD1", 
    "MONEY": "#BEFFBE",
    "NORP": "#71B4B0", 
    "ORDINAL": "#E6BEBE", 
    "ORG": "#BEBEBE",  
    "PERCENT": "#FFFFBE", 
    "PERSON": "#BEBEFF",
    "PRODUCT": "#FFD9BE", 
    "QUANTITY": "#C0C0BE", 
    "TIME": "#DDC0FF", 
    "WORK_OF_ART": "#FFEBF3", 
    "": "#F5F5F5"         
}

translate_table = [
    ["英文", "中文", "詳細釋義", "舉例"],
    ["Entity instance", "實體實例", "被劃分為某個實體類別的詞", "小明，香港"],
    ["Entity class", "實體類別", "定義某一類詞語", "人名，地名，時間"],
    ["Entity group", "實體群組", "把不同的實體實例自訂為實體群組以作合併研究", "西遊記主角（唐僧，孫悟空，豬八戒，沙和尚，白龍馬）"],
    ["Entity alias", "實體別名", "把指向同一事物的實體合併", "陳小明（小明，阿明，陳小明）"]
]

ALL_NER_TAG = {}    
ALL_NER_TAG_Color = CKIP_ALL_NER_TAG_COLORS

# "opeartor" global variables for file currently working on
text = ""                   # the full text
instances = []              # format [(ner_instance, ner_class), ...] ORDER OF FIRST APPEARANCE, all the NER instances(without duplication)
Display_inst = []           # format [ner_instance, ...] instances to be displayed
button_delete_ins = {}      # format {"instance name" : delete_button_for_this_instance}                  
instance_displayName = {}   # format {ner_instance:[freq,(AliasName, AliasFreq)], ...} the nameinfo want to display in the List
                            # contain frequency information
instance_by_class = {}      # format {ner_class:[ner_instance,....], ...} ORDER OF FIRST APPEARANCE
instance_by_group = {}      # format {GroupName:[ner_instance,....], ...} ORDER OF ADDITION (put instance want to study together in the same group)
instance_by_alias = {}    # format {AliasName:(ner_class,[ner_instance,....]), ...} ORDER OF ADDITION (combine instance, e.g. alternative name)
all_files = {}              # {"":[{"text":text},{"instances":instances}, {"instance_displayName":instance_displayName}, ...], "filename1":[{"text":text},{"instances":instances}, {"instance_displayName":instance_displayName},, ...], "filename2":[{"text":text},...]...}
                            # "" for using text area
ByFreq = False              # flag for whether the list is dsplayed by frequency in sidebar     

CurrentFile = ""            # current file working on
MULTIPLE_FILE = False       # True if using file uploading for text
FILES_WORKON = {}           # the files curently working on 
                            # {filename: uploadedfile(if any)}

###############################################################
# session_state initialization and load data
###############################################################
session_state = st.session_state.setdefault("session_state", {})    # session_state is to keep values on variables across page refreshing 

# initialization of session_state
default_session_state = {
    "ALL_NER_TAG": ALL_NER_TAG,
    "ALL_NER_TAG_Color": ALL_NER_TAG_Color,
    "text": "",
    "instances": [],
    "instance_displayName": {},
    "Display_inst": [],
    "instance_by_class": {},
    "instance_by_group": {},
    "instance_by_alias": {},
    "button_delete_ins" : {},
    "all_files" : {},
    "CurrentFile": ""
}
# no corresponding global variables
if "UploadingDef" not in session_state: # flag for whether uploading definition (when using text box)
    session_state["UploadingDef"] = False
if "UploadingDef_mul" not in session_state: # flag for whether uploading definition (when uploading text files)
    session_state["UploadingDef_mul"] = False

# load previous data from session_state
for key, value in default_session_state.items():
    if key in session_state:
        globals()[key] = session_state[key]
    else:
        globals()[key] = value

#########################################################################################################################################
#########################################################################################################################################
# function definition

###############################################################
# function: initialize(filenames)
# parameter:
#   filenames: [string]   
# author: Berry
###############################################################
def initialize(filenames):
    global all_files, FILES_WORKON
    
    for f in filenames:
        if(f not in all_files):
            all_files[f] = {}

            if FILES_WORKON[f]:
                thistext = StringIO(FILES_WORKON[f].getvalue().decode("utf-8")).read()
                all_files[f]["text"] = thistext
            else:
                all_files[f]["text"] = ""

            if ("instances" not in all_files[f]):
                all_files[f]["instances"] = []  
            if ("instance_displayName" not in all_files[f]):
                all_files[f]["instance_displayName"] = {} 
            if ("Display_inst" not in all_files[f]):
                all_files[f]["Display_inst"] = []      
            if ("instance_by_class" not in all_files[f]):
                all_files[f]["instance_by_class"] = {}
                # for c in ALL_NER_TAG:
                #     all_files[f]["instance_by_class"][c] = []
            if ("instance_by_group" not in all_files[f]):
                all_files[f]["instance_by_group"] = {}
            if ("instance_by_alias" not in all_files[f]):
                all_files[f]["instance_by_alias"] = {}
            if ("button_delete_ins" not in all_files[f]):
                all_files[f]["button_delete_ins"] = {}

    session_state["all_files"] = all_files


###############################################################
# function: LoadData(f)
# set "operator" global variables according to file
# parameter:
#   f: string  # filename 
# author: Sherry
###############################################################
def LoadData(f):
    global all_files
    GloVars = ['text', 'instances', 'instance_displayName', 'instance_by_class', 'Display_inst', 'instance_by_group','instance_by_alias', 'button_delete_ins' ]
    for key in GloVars:
        globals()[key] = all_files[f][key]
        session_state[key] = globals()[key]


###############################################################
# function: StoreData(f)
# store updated data from "operator global variables to all_files
# parameter:
#   f: string  # filename 
# author: Sherry
###############################################################
def StoreData(f):
    global all_files
    GloVars = ['text', 'instances', 'instance_displayName', 'instance_by_class', 'Display_inst', 'instance_by_group','instance_by_alias', 'button_delete_ins' ]
    for key in GloVars:
        all_files[f][key] = globals()[key]
    session_state['all_files'] = all_files


###############################################################
# function: ProcessModelResult(result)
# use result from model to upload data
# parameter:
#   result: list    # result from CKIP model
# author: Sherry
###############################################################
def ProcessModelResult(result):
    global instances, instance_displayName, instance_by_class, Display_inst, MULTIPLE_FILE

    for c in CKIP_ALL_NER_TAG:
        addClass(c, CKIP_ALL_NER_TAG[c], MULTIPLE_FILE)

    for n in result: 
        if (not (n.word, n.ner) in instances):
            AddEditInstance(n.word, n.ner, MULTIPLE_FILE)


###############################################################
# function: addGroup(newGroupName)
# To add a new empty group to the dictionary instance_by_group:
# parameter:
#   newGroupName: String
# author: Sherry
###############################################################
def addGroup(newGroupName):
    if newGroupName not in instance_by_group and newGroupName != "":
        instance_by_group[newGroupName] = []
        session_state["instance_by_group"] = instance_by_group


###############################################################
# function: delGroup(delGroupName)
# To delete a group from the dictionary instance_by_group:
# parameter:
#   newGroupName: String
# author: Sherry
###############################################################
def delGroup(delGroupName):
    if delGroupName in instance_by_group:
        del instance_by_group[delGroupName]
        session_state["instance_by_group"] = instance_by_group


###############################################################
# function: manageGroup(groupToManage, group_members)
# To modify the members in a group:
# parameter:
#   groupToManage: string
#   group_members: list
# author: Sherry
###############################################################
def manageGroup(groupToManage, group_members):
    if groupToManage in instance_by_group:
        instance_by_group[groupToManage] = group_members
        # instance_by_group[groupToManage] = []
        # for m in group_members:
        #     instanceTOList(m, instance_by_group[groupToManage])
        session_state["instance_by_group"] = instance_by_group

###############################################################
# function: addAlias(newAliasName, newAliasClass)
# To add a new empty alias to the dictionary instance_by_alias:
# parameter:
#   newAliasName: String
#   AliasClass: String
# author: Sherry
###############################################################
def addAlias(newAliasName, newAliasClass):
    if newAliasClass not in instance_by_class or newAliasName == "":
        return
    if newAliasName not in instance_by_alias:
        instance_by_alias[newAliasName] = (newAliasClass, [])
        session_state["instance_by_alias"] = instance_by_alias


###############################################################
# function: delAlias(delAliasName)
# To delete an Alias from the dictionary instance_by_alias:
# parameter:
#   newAliasName: String
# author: Sherry
###############################################################
def delAlias(delAliasName):
    if delAliasName in instance_by_alias:
        ori_members = instance_by_alias[delAliasName][1]
        for member in ori_members:
            instance_displayName[member][1] = ()
        session_state["instance_displayName"] = instance_displayName

        del instance_by_alias[delAliasName]
        session_state["instance_by_alias"] = instance_by_alias


###############################################################
# function: manageAlias(aliasToManage, alias_members)
# To modify the members in a alias:
# parameter:
#   aliasToManage: string
#   alias_members: list
# author: Sherry
###############################################################
def manageAlias(aliasToManage, alias_members):
    if aliasToManage in instance_by_alias:
        ori_members = instance_by_alias[aliasToManage][1]
        for member in ori_members:
            instance_displayName[member][1] = ()
            
        # reorderMembers = []
        # for m in alias_members:
        #     instanceTOList(m, reorderMembers)

        instance_by_alias[aliasToManage] = (instance_by_alias[aliasToManage][0], alias_members) 
        session_state["instance_by_alias"] = instance_by_alias

        A_freq = 0
        for member in alias_members:
            A_freq += instance_displayName[member][0]
        for member in alias_members:
            instance_displayName[member][1] = (aliasToManage, A_freq)
        session_state["instance_displayName"] = instance_displayName


###############################################################
# function: availForAlias(entityList, thisAlias)
# To ensure uniqueness of alias, given a list of entities, remove those already in other alias(i.e. not avaliable for thisAlias):
# parameter:
#   entityList: list        
#   thisAlias: string
# return:
#   entityList_copy: list
# author: Sherry
###############################################################
def availForAlias(entityList, thisAlias):
    entityList_copy = entityList.copy()
    entityList = entityList.copy() # avoid modification of the original list
    for en in entityList:
        if instance_displayName[en][1]:
            if instance_displayName[en][1][0] != thisAlias:
                entityList_copy.remove(en)
    return entityList_copy

###############################################################
# function: instanceTOList(instance, dest_list)
# in-place modification
# To add an instance to a list according to appearence:
# parameter:
#   instances: str              # the new instance
#   dest_list: list             # the destination list
# author: Sherry
# ###############################################################
def instanceTOList(instance, dest_list):
    global text
    if (instance in dest_list) or instance == '':
        return
    else:
        new_pos = text.index(instance)

        for i in range(len(dest_list)):
            if text.index(dest_list[i]) > new_pos:
                dest_list.insert(i, instance)
                break

        if not (instance in dest_list):
            dest_list.insert(len(dest_list)-1, instance)
    

###############################################################
# function: addClass(ClassName, ClassDescri, MultipleFile = False)
# add a class must provide description
# if provided description for existing class, description will also be updated
# parameter:
#   ClassName: str       # the class name
#   ClassDescri: str            # the description of the class
#   MultipleFile = bool     # recursive call if True
# author: Sherry
###############################################################
def addClass(ClassName, ClassDescri, MultipleFile = False):
    if len(ClassDescri) > 10:
        return
    global CurrentFile
    if MultipleFile:
        StoreData(CurrentFile)
        for file in FILES_WORKON:
            LoadData(file)
            addClass(ClassName, ClassDescri)
            StoreData(file)
            LoadData(CurrentFile)
        return

    global instance_by_class, ALL_NER_TAG, ALL_NER_TAG_Color
    if ClassDescri:
        ALL_NER_TAG[ClassName] = ClassDescri
        session_state["ALL_NER_TAG"] = ALL_NER_TAG

        if ClassName not in instance_by_class:
            instance_by_class[ClassName] = []
            session_state["instance_by_class"] = instance_by_class

        if ClassName not in ALL_NER_TAG_Color:
            ALL_NER_TAG_Color[ClassName] = NewColor(ALL_NER_TAG_Color.copy())
            session_state["ALL_NER_TAG_Color"] = ALL_NER_TAG_Color


###############################################################
# function: NewColor(existing_colors)
# new distinct color
# parameter: 
#     existing_colors： dict
# author: Sherry
###############################################################
def NewColor(existing_colors):
    light_colors = [
        "#ABB471", "#FA90AB", "#FA90EF", "#909EFA", "#90FAC2", "#90F4FA", "#F7A598",
        "#F7C598", "#E8CF8C", "#E88CAB", "#8CE8C5", "#8CC2E8", "#E8C08C", "#8796D5"
    ]

    # Check if any predefined light color is available
    for color in light_colors:
        if color not in existing_colors.values():
            return color

    # Generate new light color programmatically
    hue_increment = 360 // len(existing_colors)
    hue = 0
    saturation = 70
    lightness = 85

    while True:
        new_color = f"hsl({hue}, {saturation}%, {lightness}%)"
        if new_color not in existing_colors.values():
            return new_color
        hue = (hue + hue_increment) % 360
        lightness = (lightness + 5) % 100


###############################################################
# function: AddEditInstance(instance, ner_tag, MultipleFile=False)
# add / edit instance in the list "instances", dictionary "instance_by_class", "instance_displayName", in order of first appearance:
# parameter:
#   instances: str       # the new instance
#   ner_tag: str            # the tag of the new instance
#   MultipleFile
# author: Sherry
###############################################################
def AddEditInstance(instance, ner_tag, MultipleFile=False):
    global instances, text, instance_by_class, instance_displayName, instance_by_alias, CurrentFile

    if MultipleFile:
        StoreData(CurrentFile)
        for file in FILES_WORKON:
            LoadData(file)
            AddEditInstance(instance, ner_tag)
            StoreData(file)
            LoadData(CurrentFile)
        return
    # edit in instances
    if ( (instance == '') or (instance not in text) or (ner_tag not in ALL_NER_TAG) ):
        return 
    else:
        new_pos = text.index(instance)
        temp = []
        for i in range(len(instances)):
            if instances[i][0] == instance: # skip previous matching -> edit
                continue
            elif text.index(instances[i][0]) < new_pos: # appear before
                temp.append(instances[i])
            else: # appear after
                temp.append((instance, ner_tag))
                temp.extend(list(inst for inst in instances[i:]))
                break
        if not ((instance, ner_tag) in temp):
            temp.append((instance, ner_tag))
        instances = temp
        session_state["instances"] = instances

    for nerlabel in ALL_NER_TAG.keys():
        instance_by_class[nerlabel] = []
    for inst, nerlabel in instances:
        instance_by_class[nerlabel].append(inst)
    session_state["instance_by_class"] = instance_by_class

    # add to display name if needed
    if not (instance in instance_displayName):
        instance_displayName[instance] = [int(0), ()]
        index = 0
        while index < len(text):
            if index + len(instance) < len(text):
                if text[index:index+len(instance)] == instance:
                    instance_displayName[instance][0] += 1
                    index += len(instance)
                    continue
            index += 1
        session_state['instance_displayName'] = instance_displayName

    # delete from Alias if tag changed
    for A in instance_by_alias.keys():
        if instance in instance_by_alias[A][1] and ner_tag != instance_by_alias[A][0]:
            modi_members = instance_by_alias[A][1].copy()
            modi_members.remove(instance)
            manageAlias(A, modi_members)


###############################################################
# function: SampleDefinition()
# privide a sample for uploading definition
# return: href     
# author: Sherry
###############################################################
def SampleDefinition():
    sampleDef = {"Class_Label":["PERSON", "TIME"], "Class_Description":["人物", "時間"], 
                "Instance_List": [ "許獻忠, 蕭輔漢", "夜間, 一夜, 今夜" ]}
    sampleDef = pd.DataFrame(sampleDef)
    csv = sampleDef.to_csv(index = False, encoding = 'utf-8')
    b64 = base64.b64encode(csv.encode()).decode()  # Encoding the CSV data
    href = f'<a href="data:file/csv;base64,{b64}" download="SampleDefiniton.csv">下載自定義範例 Download a CSV file template here</a>'
    return href


###############################################################
# function: processDefinition(dict_def)
# process uploaded definition
# parameter:
#   df_def: dataframe     
# author: Sherry
###############################################################
def processDefinition(df_def):
    global text, instances, instance_by_class, instance_displayName, instance_by_alias

    index_list = ["Class_Label", "Class_Description", "Instance_List"]
    df_def.rename({i:index_list[i] for i in range(len(index_list))}, axis='columns', inplace=True)
    for index in range(len(df_def)):
        nerLabel = df_def["Class_Label"][index]
        global MULTIPLE_FILE
        addClass(nerLabel, df_def["Class_Description"][index], MULTIPLE_FILE)
        this_instList = str(df_def["Instance_List"][index])
        this_instList = this_instList.replace(' ', '')
        this_instList = this_instList.split(",")
        for entity in this_instList:
            if (entity, nerLabel) not in instances:
                AddEditInstance(entity, nerLabel, MULTIPLE_FILE)

###############################################################
# function: DisplayListByFreq(DisplayList, forAlias = False)
# rearrange the DisplayList by frequency
# parameter:
#   DisplayList: list, better called by value i.e. DisplayList.copy()
#   forAlias: bool  
# return:
#   ListbyFreq: list
# author: Sherry
###############################################################
def DisplayListByFreq(DisplayList, forAlias = False):
    DisplayList = DisplayList.copy() # avoid modification of the original list
    ListbyFreq = []
    handeledByAlias = []
    for inst in DisplayList:
        if inst in handeledByAlias:
            continue
        if (instance_displayName[inst][1] != ()) and (not forAlias):
            sameAlias = []
            A_name = instance_displayName[inst][1][0]
            A_members = instance_by_alias[A_name][1]
            for SAInst in A_members:
                if SAInst in DisplayList:
                    sameAlias.append(SAInst)
                    handeledByAlias.append(SAInst)
            sameAlias = DisplayListByFreq(sameAlias.copy(), True)
            sameAlias = [ (item, instance_displayName[inst][1][1]) for item in sameAlias]
            ListbyFreq.extend(sameAlias)
        else:
            ListbyFreq.append( (inst, instance_displayName[inst][0]) )

    ListbyFreq = sorted(ListbyFreq, key=lambda x: x[1], reverse=True)
    ListbyFreq = [item[0] for item in ListbyFreq]
    return ListbyFreq
        
    
###############################################################
# function: DisplayNERAnnotation(instances, text)
# to display full text with NER annotated
# parameter:
#   instances: list       # a list of all NER in format [(ner_instance, ner_class), ...]
#   text: string             # a stirng of full text
# author: Sherry
###############################################################
def DisplayNERAnnotation(instances, text, Display_inst):
    
    annotated_words = []
    index = 0
    while index < len(text):
        flag = False
        for inst in instances: 
            word = inst[0]
            if not (word in Display_inst):
                continue
            if index + len(word) < len(text):
                if text[index:index+len(word)] == word:
                    annotated_words.append((word, inst[1], ALL_NER_TAG_Color[inst[1]]))
                    flag = True
                    index += len(word)
                    break
        if flag == False:
            annotated_words.append(text[index])
            index += 1
    
    with stylable_container(
            key="aText",
            css_styles="""
                {
                    overflow-y: scroll;
                    max-height: 300px;
                    border: 1px #dcdcdc solid;
                    border-radius: 5px;
                    padding: 10px;
                }
                """,
        ):
        annotated_text(annotated_words)

###############################################################
# function: delete_ins(inst, MultipleFile = False)
# to delete instances
# parameter: instance: string 
#            MultipleFile: bool
# author: Berry
###############################################################

def delete_ins(inst, MultipleFile = False):
    global instances, instance_displayName, instance_by_class, instance_by_group, instance_by_alias, Display_inst, CurrentFile
    
    if MultipleFile:
        StoreData(CurrentFile)
        for file in FILES_WORKON:
            LoadData(file)
            delete_ins(inst)
            StoreData(file)
            LoadData(CurrentFile)
        return
    
    if inst not in instance_displayName:
        return
    
    for i,c in instances:
        if i == inst:
            selected_class = c

    instances = [instance for instance in instances if instance[0] != inst]
    
    instance_by_class[selected_class] = [instance for instance in instance_by_class[selected_class] if instance != inst]
    
    for g in instance_by_group:
        if inst in instance_by_group[g]:
            instance_by_group[g].remove(inst)

    for a in instance_by_alias:
        if inst in instance_by_alias[a][1]:
            memberList = instance_by_alias[a][1].copy()
            memberList.remove(inst)
            manageAlias(a, memberList)

    del instance_displayName[inst]

    if inst in Display_inst:
        Display_inst.remove(inst)

    session_state["instances"] = instances
    session_state["instance_by_class"] = instance_by_class
    session_state["instance_by_group"] = instance_by_group
    session_state["instance_by_alias"] = instance_by_alias
    session_state["Display_inst"] = Display_inst


###############################################################
# function:delClass(ClassName, MultipleFile = False)
# to delete a class
# parameter: ClassName: String
#            MultipleFile: bool
# author: sherry
###############################################################
def delClass(ClassName, MultipleFile = False):
    global ALL_NER_TAG, ALL_NER_TAG_Color, instance_by_class, CurrentFile
    if MultipleFile:
        StoreData(CurrentFile)
        for file in FILES_WORKON:
            LoadData(file)
            delClass(ClassName)
            StoreData(file)
            LoadData(CurrentFile)
        return
    
    if (ClassName not in ALL_NER_TAG): 
        return
    else:
        for inst in instance_by_class[ClassName]:
            delete_ins(inst, MULTIPLE_FILE)
        for A in instance_by_alias:
            if instance_by_alias[A][0] == ClassName:
                delAlias(A)
        del instance_by_class[ClassName]
        del ALL_NER_TAG[ClassName]
        del ALL_NER_TAG_Color[ClassName]
        session_state["instance_by_class"] = instance_by_class
        session_state["ALL_NER_TAG"] = ALL_NER_TAG
        session_state["ALL_NER_TAG_Color"] = ALL_NER_TAG_Color


#########################################################################################################################################
#########################################################################################################################################
# functions for Data Export

###############################################################
# function: export_csv_zip(dataframes)
# to export data stored in "operator" global variables, i.e. Currentfile
# parameter: datframes 
# author: Sherry
###############################################################
def export_csv_zip(dataframes):
    # Create a ZIP file object
    filenames = {"df_E": "Entity.csv", "df_G": "Group.csv", "df_A":"Alias.csv"}
    with zipfile.ZipFile('data.zip', 'w') as zipf:
        for name, df in dataframes.items():
            if name in filenames:
                file_name = filenames[name]
            else:
                file_name = f'{name}.csv'
            
            # Convert the dataframe to a CSV string
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            # Add the CSV string to the ZIP file with the custom filename
            zipf.writestr(file_name, csv_data)

    # Provide a download link for the ZIP file
    with open('data.zip', 'rb') as f:
        zip_data = f.read()
    st.download_button('下載 ZIP 文件', data=zip_data, file_name='data.zip', mime='application/zip')

def DataFrame_ALL(instances, instance_by_group, instance_by_alias, instance_displayName):
    df_E = {'ID_E':[], 'Entity':[], 'EntityClass':[], 'Frequency': [], 'Relations': [], 'Relation_Name': []}
    df_G = {'ID_G':[], 'GroupName':[], 'GroupFrequency':[], 'GroupMembers':[], 'GroupMembers_Name':[]}
    df_A = {'ID_A':[], 'AliasName':[], 'AliasClass':[], 'AliasFrequency':[], 'AliasMembers':[], 'AliasMembers_Name':[]}

    # Data of Entity
    df_E["ID_E"] = range(0,len(instances))
    df_E["ID_E"] = ['E'+str(item) for item in df_E["ID_E"]]
    df_E["Entity"] = [item[0] for item in instances]
    df_E["EntityClass"] = [item[1] for item in instances]
    df_E["Frequency"] = [instance_displayName[item][0] for item in df_E["Entity"]]
    df_E["Relations"] = [[] for item in df_E["Entity"]]
    df_E["Relation_Name"] = [[] for item in df_E["Entity"]]

    # Data of Group
    i = 0
    for G in instance_by_group.keys():
        df_G["ID_G"].append('G'+str(i))
        df_G["GroupName"].append(G)
        thisMembers = []
        thisMembers_name = []
        G_freq = 0
        for m in instance_by_group[G]:
            index = df_E["Entity"].index(m)
            thisMembers.append(df_E["ID_E"][index])
            thisMembers_name.append(df_E["Entity"][index])
            df_E["Relations"][index].append('G'+str(i))
            df_E["Relation_Name"][index].append(G)
            G_freq += instance_displayName[m][0]
        df_G["GroupMembers"].append(thisMembers)
        df_G["GroupMembers_Name"].append(thisMembers_name)
        df_G["GroupFrequency"].append(G_freq)
        i += 1

    # Data for Alias
    i = 0
    for A in instance_by_alias.keys():
        df_A["ID_A"].append('A'+str(i))
        df_A["AliasName"].append(A)
        df_A["AliasClass"].append(instance_by_alias[A][0])
        A_freq = 0
        if instance_by_alias[A][1]:
            m = instance_by_alias[A][1][0]
            A_freq = instance_displayName[m][1][1]
        df_A["AliasFrequency"].append(A_freq)
        thisMembers = []
        thisMembers_name = []
        for m in instance_by_alias[A][1]:
            index = df_E["Entity"].index(m)
            thisMembers.append(df_E["ID_E"][index])
            thisMembers_name.append(df_E["Entity"][index])
            df_E["Relations"][index].append('A'+str(i))
            df_E["Relation_Name"][index].append(A)
        df_A["AliasMembers"].append(thisMembers)
        df_A["AliasMembers_Name"].append(thisMembers_name)
        i += 1

    dfs = {"df_E": pd.DataFrame(df_E), "df_G":pd.DataFrame(df_G), "df_A": pd.DataFrame(df_A)}
    return dfs

#########################################################################################################################################
#########################################################################################################################################
# main page
# st.caption("Chinese Named-Entity Recognition (NER) Tool")
st.markdown("<p style='font-weight:600;font-size:26px;margin-bottom:-8px;'>Chinese Named-Entity Recognition (NER) Tool</p>", unsafe_allow_html=True)
st.title("中文自動標注實體實例平台")

#########################################################################################################################################
#########################################################################################################################################
# session 1: text specification
st.markdown("---")
st.subheader("• " + "文本導入")
st.markdown("###")

# using file uploader
uploaded_files = st.file_uploader("方法一：上載 txt 檔案。:red[請使用唯一的檔案名，否則會出現衝突。]", accept_multiple_files=True, type = ["txt"])
if uploaded_files:
    MULTIPLE_FILE = True
    num_files = len(uploaded_files)
    filenames = []

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        filenames.append(filename)
        FILES_WORKON[filename] = uploaded_file

    initialize(filenames)

    #########################################################################################################################################
    #########################################################################################################################################
    # session 2: text annotation
    st.markdown("---")
    st.subheader("• " + "文本標注")
    CurrentFile = st.selectbox('選擇要處理的檔案：',filenames)
    session_state["CurrentFile"] = CurrentFile
    LoadData(CurrentFile)

    ###############################################################
    # button definition
    # Buttons: "Auto Annotate", "Clear_Annotations"
    ###############################################################
    st.write("以下功能自動應用於所有文件。")
    col1, col2, col3 = st.columns(3)

    with col3:
        UploadingDef_mul = st.checkbox("上傳自定義實體類別\n\n Upload Self-Defined Entity Class with Instances", value = session_state["UploadingDef_mul"])
        session_state["UploadingDef_mul"] = UploadingDef_mul

    with col1:
        with stylable_container(
            key="autoAnnotate_button",
            css_styles="""
                button {
                    background-color: #ff4c4b;
                    color: white;
                }
                """,
        ):
            Auto_Annotate = st.button("開始自動標注\n\n Start Auto-Annotation")

    with col2:
        manualAddInst =  st.checkbox("手動標注實體實例\n\n Annotate Entity Manually")

    ###############################################################
    # upload definition
    # Sherry
    ###############################################################
    if UploadingDef_mul:
        uploaded_definition = st.file_uploader("上傳自定義實體類別", type = ["csv"])
        if uploaded_definition:
            df_defi = pd.read_csv(uploaded_definition)
            processDefinition(df_defi)
            st.success("自定義檔案已成功處理。")
            session_state["UploadingDef_mul"] = False
        st.markdown(SampleDefinition(), unsafe_allow_html=True)

    ###############################################################
    # Button: "Auto Annotate"
    # author: Sherry
    ###############################################################
    if Auto_Annotate:

        # run CKIP to auto recognize NER
        # result = ner_driver([text])
        # result = list(itertools.chain(*result)) # fallten to 1D list
        # ProcessModelResult(result)

        StoreData(CurrentFile)

        for file in FILES_WORKON:
            thisText = all_files[file]["text"]
            result = ner_driver([thisText])
            result = list(itertools.chain(*result)) # fallten to 1D list
            ProcessModelResult(result)

        LoadData(CurrentFile)

    ###############################################################
    # "Mark a word as an entity"
    # author: Berry
    ###############################################################
    if manualAddInst:
        if ALL_NER_TAG:
            words = st.text_input("輸入您要標記的詞語: ")
            boxOptions = [f"{value}|{key}" for key, value in ALL_NER_TAG.items()]
            ner_m = st. selectbox("實體類別: ", boxOptions)
            confirm = st.button("新增或修改")
            # words = list(words)
            if confirm:
                if words: 
                    AddEditInstance(words,ner_m.split("|")[1], MULTIPLE_FILE)
        else: 
            st.write('暫無實體類別， 無法標記。')
    
    st.write("以下功能僅應用於當前文件。")
    ###############################################################
    # button: data export
    # author: Sherry
    ###############################################################
    with col1:
        st.markdown("---")
        st.write("以下功能僅應用於當前文件。")
        with stylable_container(
            key="dataExport_button1",
            css_styles="""
                button {
                    background-color: #0060c0;
                    color: white;
                }
                """,
            ):
            if st.button("導出實體數據\n\n Export Entities Data"):
                dfs = DataFrame_ALL(instances.copy(), instance_by_group.copy(), instance_by_alias.copy(), instance_displayName.copy())
                export_csv_zip(dfs)


# using text input area
if not uploaded_files:
    MULTIPLE_FILE = False
    CurrentFile = ""
    FILES_WORKON[""] = None
    initialize([""])
    LoadData(CurrentFile)


    default_text = "包公案－龍圖公案\t第一則\t\t阿彌陀佛講和 sample text source: http://open-lit.com/book.php?bid=189\n\n話說德安府孝感縣有一秀才，姓許名獻忠，年方十八，生得眉清目秀，豐潤俊雅。對門有一屠戶蕭輔漢，有一女兒名淑玉，年十七歲，甚有姿色，姑娘大門不出，每日在樓上繡花。\n\n其樓靠近街路，常見許生行過，兩下相看，各有相愛的心意。\n\n時日積久，遂私下言笑，許生以言挑之，女即微笑首肯。這夜，許生以樓梯暗引上去，與女攜手蘭房，情交意美。及至雞鳴，許生欲歸，暗約夜間又來。淑玉道：「倚梯在樓，恐夜間有人經過看見你。我今備一圓木在樓枋上，將白布一匹，半掛圓木，半垂樓下。你夜間只將手緊抱白布，我在樓上吊扯上來，豈不甚便。」許生喜悅不勝，至夜果依計而行。如此往來半年，鄰舍頗知，只瞞得蕭輔漢一人。\n\n忽一夜，許生因朋友請酒，夜深未來。有一和尚明修，夜間叫街，見樓上垂下白布到地，只道其家曬布未收，思偷其布，遂停住木魚，過去手扯其布。忽然樓上有人弔扯上去，和尚心下明白，必是養漢婆娘垂此接奸上去，任她弔上去。果見一女子，和尚心中大喜，便道：「小僧與娘子有緣，今日肯捨我宿一宵，福田似海，恩大如天。」淑玉慌了道：「我是鸞交鳳配，怎肯失身於你？我寧將銀簪一根舍於你，你快下樓去。」僧道：「是你弔我上來，今夜來得去不得了。」即強去摟抱求歡。女甚怒，高聲叫道：「有賊在此！」那時女父母睡去不聞。僧恐人知覺，即拔刀將女子殺死。取其簪、耳環、戒指下樓去。\n\n次日早飯後，其母見女兒不起，走去看時，見被殺死在樓，竟不知何人所謀。其時鄰舍有不平許生事者，與蕭輔漢道：「你女平素與許獻忠來往有半年餘，昨夜許生在友家飲酒，必定乘醉誤殺，是他無疑。」蕭輔漢聞知包公神明，即送狀赴告：「告為強姦殺命事：學惡許獻忠，心邪狐媚，行丑鶉奔。\n\n覘女淑玉艾色，百計營謀，千思污辱。昨夜，帶酒佩刀，潛入臥室，摟抱強姦，女貞不從，拔刀刺死。遺下簪珥，乘危盜去。\n\n鄰右可證。托跡黌門，桃李陡變而為荊榛；駕稱泮水，龍蛇忽轉而為鯨鱷。法律實類鴻毛，倫風今且塗地。急控填償，哀哀上告。」\n\n是時包公為官極清，識見無差。當日准了此狀，即差人拘原、被告和干證人等聽審。\n\n包公先問干證，左鄰蕭美、右鄰吳范俱供：蕭淑玉在沿街樓上宿，與許獻忠有奸已經半載，只瞞過父母不知，此奸是有的，並非強姦，其殺死緣由，夜深之事眾人實在不知。許生道：「通姦之情瞞不過眾人，我亦甘心肯認。若以此擬罪，死亦無辭；但殺死事實非是我。」蕭輔漢道：「他認輕罪而辭重罪，情可灼見。女房只有他到，非他殺死，是誰殺之？必是女要絕他勿奸，因懷怒殺之。且後生輕狂性子，豈顧女子與他有情？老爺若非用刑究問，安肯招認？」包公看許生貌美性和，似非兇惡之徒，因此問道：「你與淑玉往來時曾有人從樓下過否？」\n\n答道：「往日無人，只本月有叫街和尚夜間敲木魚經過。」包公聽罷怒道：「此必是你殺死的。今問你罪，你甘心否？」獻忠心慌，答道：「甘心。」遂打四十收監。包公密召公差王忠、李義問道：「近日叫街和尚在何處居住？」王忠道：「在玩月橋觀音座前歇。」包公吩咐二人可密去如此施行。\n\n是夜，僧明修又敲木魚叫街，約三更時分，將歸橋宿，只聽得橋下三鬼一聲叫上，一聲叫下，又低聲啼哭，甚是淒切怕人。僧在橋打坐，口念彌陀。後一鬼似婦人之聲，且哭且叫道：「明修明修，你要來奸我，我不從罷了，我陽數未終，你無殺我的道理。無故殺我，又搶我釵珥，我已告過閻王，命二鬼吏伴我來取命，你反念阿彌陀佛講和；今宜討財帛與我並打發鬼伎，方與私休，不然再奏天曹，定來取命。念諸佛難保你命。」\n\n明修乃手執彌陀珠佛掌答道：「我一時慾火要奸你，見你不從又要喊叫，恐人來捉我，故一時誤殺你。今釵珥戒子尚在，明日買財帛並唸經卷超度你，千萬勿奏天曹。」女鬼又哭，二鬼又叫一番，更覺悽慘。僧又唸經，再許明日超度。忽然，兩個公差走出來，用鐵鏈鎖住僧。僧驚慌道：「是鬼？」王忠道：「包公命我捉你，我非鬼也。」嚇得僧如泥塊，只說看佛面求赦。\n\n王忠道：「真好個謀人佛，強姦佛。」遂鎖將去。李義收取禪擔、蒲團等物同行。原來包公早命二差僱一娼婦，在橋下作鬼聲，嚇出此情。\n\n次日，鎖了明修並帶娼婦見包公，敘橋下做鬼嚇出明修要強姦不從因致殺死情由。包公命取庫銀賞了娼家並二公差去訖。\n\n又搜出明修破衲襖內釵、珥、戒指，叫蕭輔漢認過，確是伊女插戴之物。明修無詞抵飾，一並供招，認承死罪。\n\n包公乃問許獻忠道：「殺死淑玉是此禿賊，理該抵命；但你秀才奸人室女，亦該去衣衿。今有一件，你尚未娶，淑玉未嫁，雖則兩下私通，亦是結髮夫妻一般。今此女為你垂布，誤引此僧，又守節致死，亦無玷名節，何愧於婦道？今汝若願再娶，須去衣衿；若欲留前程，將淑玉為你正妻，你收埋供養，不許再娶。此二路何從？」獻忠道：「我深知淑玉素性賢良，只為我牽引故有私情，我別無外交，昔相通時曾囑我娶她，我亦許她發科時定媒完娶。不意遇此賊僧，彼又死節明白，我心豈忍再娶？今日只願收埋淑玉，認為正妻，以不負她死節之意，決不敢再娶也。其衣衿留否，惟憑天台所賜，本意亦不敢欺心。」\n\n包公喜道：「汝心合乎天理，我當為你力保前程。」即作文書申詳學道：審得生員許獻忠，青年未婚；鄰女淑玉，在室未嫁。兩少相宜，靜夜會佳期於月下，一心合契，半載赴私約於樓中。方期緣結乎百年，不意變生於一旦。惡僧明修，心猿意馬，夤夜直上重樓。狗幸狼貪，糞土將污白璧。謀而不遂，袖中抽出鋼刀。死者含冤，暗裡剝去釵珥。傷哉淑玉，遭凶僧斷喪香魂；義矣獻忠，念情妻誓不再娶。今擬僧抵命，庶雪節婦之冤；留許前程，少獎義夫之慨，未敢擅便，伏候斷裁。\n\n學道隨即依擬。後許獻忠得中鄉試，歸來謝包公道：「不有老師，獻忠已做囹圄之鬼，豈有今日？」包公道：「今思娶否？」許生道：「死不敢矣。」包公道：「不孝有三，無後為大。」許生道：「吾今全義，不能全孝矣。」包公道：「賢友今日成名，則蕭夫人在天之靈必喜悅無窮。就使若在，亦必令賢友置妾。今但以蕭夫人為正，再娶第二房令閫何妨。」獻忠堅執不從。包公乃令其同年舉人田在懋為媒，強其再娶霍氏女為側室。獻忠乃以納妾禮成親。其同年錄只填蕭氏，不以霍氏參入，可謂婦節夫義，兩盡其道。而包公雪冤之德，繼嗣之恩，山高海深矣！"
    if text != "":
        default_text = text
    
    st.markdown("###")
    new_text = st.text_area("方法二：請輸入您的文字", default_text, 300)

    if text == "":
        if st.button("確認應用文本"):
            text = new_text
            session_state["text"] = text
            StoreData(CurrentFile)

    else:
        if st.button("清除數據並應用新文本"):
            del all_files[CurrentFile]
            initialize([""])
            LoadData(CurrentFile)
            text = new_text
            session_state["text"] = text
            StoreData(CurrentFile)

    if text:
        #########################################################################################################################################
        #########################################################################################################################################
        # session 2: text annotation
        st.markdown("---")
        st.subheader("• " + "文本標注")
        st.markdown("#")

        col1, col2, col3= st.columns(3)
        with col3:
            UploadingDef = st.checkbox("上傳自定義實體類別\n\n Upload Self-Defined Entity Class with Instances", value = session_state["UploadingDef"])
            session_state["UploadingDef"] = UploadingDef

        with col1:
            with stylable_container(
                key="autoAnnotate_button",
                css_styles="""
                    button {
                        background-color: #ff4c4b;
                        color: white;
                    }
                    """,
            ):
                Auto_Annotate = st.button("開始自動標注\n\n Start Auto-Annotation")

        with col2:
            manualAddInst =  st.checkbox("手動標注實體實例\n\n Annotate Entity Manually")


        ###############################################################
        # upload definition
        # Sherry
        ###############################################################
        if UploadingDef:
            st.markdown(SampleDefinition(), unsafe_allow_html=True)
            st.image("manual-img/sample-definition-csv.png", width=400, caption="範例 Example")
            uploaded_definition = st.file_uploader("上傳您的自定義實體類別", type = ["csv"])
            if uploaded_definition:
                df_defi = pd.read_csv(uploaded_definition)
                processDefinition(df_defi)
                st.success("自定義檔案已成功處理。")
                session_state["UploadingDef"] = False

        ###############################################################
        # Button: "Auto Annotate"
        # author: Sherry
        ###############################################################
        if Auto_Annotate:
            # run CKIP to auto recognize NER
            result = ner_driver([text])
            result = list(itertools.chain(*result)) # fallten to 1D list
            ProcessModelResult(result)

        ###############################################################
        # "Mark a word as an entity"
        # author: Berry
        ###############################################################
        if manualAddInst:
            if ALL_NER_TAG:
                words = st.text_input("輸入您要標記的詞語: ")
                boxOptions = [f"{value}|{key}" for key, value in ALL_NER_TAG.items()]
                ner_m = st. selectbox("實體類別: ", boxOptions)
                confirm = st.button("新增或修改")
                # words = list(words)
                if confirm:
                    if words: 
                        AddEditInstance(words,ner_m.split("|")[1], MULTIPLE_FILE)
            else: 
                st.write('暫無實體類別， 無法標記。')

        ###############################################################
        # button: data export
        # author: Sherry
        ###############################################################
        with col1:
            with stylable_container(
                key="dataExport_button2",
                css_styles="""
                    button {
                        background-color: #0060c0;
                        color: white;
                    }
                    """,
                ):
                if st.button("導出實體數據\n\n Export Entities Data"):
                        dfs = DataFrame_ALL(instances.copy(), instance_by_group.copy(), instance_by_alias.copy(), instance_displayName.copy())
                        export_csv_zip(dfs)


#########################################################################################################################################
#########################################################################################################################################
# sidebar

with st.sidebar:

    st.markdown("""
                <a href="https://library.hkust.edu.hk/"><img src="https://library.hkust.edu.hk/wp-content/themes/hkustlib/hkust_alignment/core/assets/library/library_logo.png_transparent_bkgd_h300.png" alt="HKUST Library Logo" style="width:200px;"/></a>
                """, unsafe_allow_html=True)

    """
    [![Manual guide](https://img.shields.io/badge/使用手冊Manual-red.svg)](https://github.com/hkust-lib-ds/P001-PUBLIC_Chinese-NER-Tool/blob/main/manual.md)
    [![GitHub repo](https://badgen.net/badge/icon/GitHub/black?icon=github&label)](https://github.com/hkust-lib-ds/P001-PUBLIC_Chinese-NER-Tool) 

    """

    ###############################################################
    # instance display list and management of class, group, alias
    # author: Sherry
    ###############################################################

    display_options = ["實體實例(Entity Instance)", "實體類別(Entity Class)", "實體群組(Entity Group)", "實體別名(Entity Alias)"]
    selected_option = st.sidebar.radio("選擇顯示方式", display_options)


    ###############################################################
    # "Check the details of professional terms"
    # author: Berry
    ###############################################################
    with st.popover("查看以上4種方式的解釋及例子"):
        # st.table(translate_table)
        df = pd.DataFrame(translate_table[1:],columns=translate_table[0]) # , columns=translate_table[0]
        df = df.set_index(df.columns[0])  # 设置第一列为新的索引
        # df = df.reset_index(drop=True)  # 重置索引为默认的整数索引，并丢弃原始索引列
        st.table(df)  # 显示修改后的DataFrame


    ###############################################################
    # "All Instances"
    # author: Sherry
    ###############################################################
    ByFreq = st.checkbox("按頻率對實體實例排序\n\n Sort by frequency")

    if selected_option == "實體實例(Entity Instance)":
        if instances == []:
            st.markdown('<p style="color:red;">暫無數據，請先開始標注。</p>', unsafe_allow_html=True)

        else:

            # instance display
            st.markdown('<p style="color:red;">若想在側邊欄刪除請多點擊一次刪除鍵。</p>', unsafe_allow_html=True)
            DisplayList = [item[0] for item in instances]
            if ByFreq:
                DisplayList = DisplayListByFreq(DisplayList.copy())
            DisplayList = [key for key in DisplayList if key in list(set(DisplayList))]
            for inst in DisplayList:
                freq = instance_displayName[inst][0]
                if instance_displayName[inst][1] != ():
                    A_name = instance_displayName[inst][1][0]
                    A_freq = instance_displayName[inst][1][1]
                    col1, col2 = st.columns(2)
                    with col1:
                        st.button(f"{inst}|{A_name} ({freq}|{A_freq} 次)")
                    with col2:    
                        button_delete_ins[inst] = st.button("刪除",key=f"delete_button_{inst}")
                        if button_delete_ins[inst]:
                            delete_ins(inst, MULTIPLE_FILE)
                    
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.button(f"{inst} ({freq} 次)")
                    with col2:    
                        button_delete_ins[inst] = st.button("刪除",key=f"delete_button_{inst}")
                        if button_delete_ins[inst]:
                            delete_ins(inst, MULTIPLE_FILE)
                            
            Display_inst = []
            Display_inst.extend(list(instance_by_class[c] for c in instance_by_class.keys()))
            Display_inst = list(itertools.chain(*Display_inst)) # fallten
            session_state["Display_inst"] = Display_inst
    
    ###############################################################
    # "Entity Class"
    # author: Sherry
    ###############################################################
    if selected_option == "實體類別(Entity Class)":
        if instance_by_class  == {}:
            st.write("暫無數據，請先標注實體實例。")
        else:
            C_options = ["顯示", "管理實體類別"]
            C_selected_option = st.sidebar.radio("選擇一個功能", C_options)

            # manage class
            if C_selected_option == "管理實體類別":
                if MULTIPLE_FILE:
                    st.write("該功能自動應用於所有文件。")

                ClassName = st.text_input("請輸入實體類別的名稱（名稱必須是唯一的）：", placeholder="PERSON")
                ClassDescri = st.text_input("請輸入實體類別的中文描述（僅用於新增）： ", placeholder="人物（10字以内）")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("創建"):
                        addClass(ClassName, ClassDescri, MULTIPLE_FILE)
                with col2:
                    if st.button("刪除"):
                        delClass(ClassName, MULTIPLE_FILE)

            # Display
            if C_selected_option == "顯示":
                boxOptions = []
                for c in instance_by_class.keys():
                    if len(instance_by_class[c]) != 0 and c in ALL_NER_TAG:
                        boxOptions.append(ALL_NER_TAG[c] + "|" + c + "  ("+ str(len(instance_by_class[c])) + " 實體實例)")
                for c in instance_by_class.keys():
                    if len(instance_by_class[c]) == 0 and c in ALL_NER_TAG:
                        boxOptions.append(ALL_NER_TAG[c] + "|" + c + "  (0 實體實例)")
                selected = st.sidebar.selectbox("選擇實體類別", boxOptions)
                selected_class = selected.split("|")[1].split("  (")[0]
                Display_inst = instance_by_class[selected_class]
                session_state["Display_inst"] = Display_inst

                DisplayList = instance_by_class[selected_class]
                if ByFreq:
                    DisplayList = DisplayListByFreq(DisplayList.copy())
                DisplayList = [key for key in DisplayList if key in list(set(DisplayList))]
                for inst in DisplayList:
                    freq = instance_displayName[inst][0]
                    if instance_displayName[inst][1] != ():
                        A_name = instance_displayName[inst][1][0]
                        A_freq = instance_displayName[inst][1][1]
                        st.button(f"{inst}|{A_name} ({freq}|{A_freq} 次)")
                    else:
                        st.button(f"{inst} ({freq} 次)")

    ###############################################################
    # "Entity Group"
    # author: Sherry
    ###############################################################
    if selected_option == "實體群組(Entity Group)":
        if instance_by_class == {}:
            st.write("暫無數據，請先標注實體實例。")
        else:
            G_options = ["顯示", "管理實體群組"]
            G_selected_option = st.sidebar.radio("選擇一個功能", G_options)

            if G_selected_option == "管理實體群組":
                if MULTIPLE_FILE:
                    st.write("該功能僅應用於當前文件。")

                GroupName = st.text_input("請輸入實體群組的名稱（名稱必須是唯一的）：")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("創建"):
                        addGroup(GroupName)
                with col2:
                    if st.button("刪除"):
                        delGroup(GroupName)

                groupToManage = st.selectbox("請選擇要管理的實體群組", list(instance_by_group.keys()), None)
                if groupToManage in instance_by_group:

                    allEntities = []
                    for c in instance_by_class.keys():
                        if len(instance_by_class[c]) != 0:
                            allEntities.extend(instance_by_class[c])

                    defaultGMember = instance_by_group[groupToManage]
                    group_members = st.multiselect("修改成員", allEntities, defaultGMember)
                    manageGroup(groupToManage, group_members)

                    Display_inst = instance_by_group[groupToManage]
                    session_state["Display_inst"] = Display_inst
                else:
                    Display_inst = []
                    session_state["Display_inst"] = Display_inst

            if G_selected_option == "顯示":
                selected_group = st.selectbox("選擇實體群組", list(instance_by_group.keys()))
                if selected_group in instance_by_group:

                    Display_inst = instance_by_group[selected_group]
                    session_state["Display_inst"] = Display_inst

                    DisplayList = []
                    for m in instance_by_group[selected_group]:
                        instanceTOList(m, DisplayList)
                    
                    if ByFreq:
                        DisplayList = DisplayListByFreq(DisplayList.copy())
                    DisplayList = [key for key in DisplayList if key in list(set(DisplayList))]
                    for inst in DisplayList:
                        freq = instance_displayName[inst][0]
                        if instance_displayName[inst][1] != ():
                            A_name = instance_displayName[inst][1][0]
                            A_freq = instance_displayName[inst][1][1]
                            st.button(f"{inst}|{A_name} ({freq}|{A_freq} 次)")
                        else:
                            st.button(f"{inst} ({freq} 次)")
                else:
                    st.write("暫無數據，請先創建實體群組。")
                    Display_inst = []
                    session_state["Display_inst"] = Display_inst
        
    ###############################################################
    # "Entity Alias"
    # author: Sherry
    ###############################################################
    if selected_option == "實體別名(Entity Alias)":
        if instance_by_class == {}:
            st.write("暫無數據，請先標注實體實例。")
        else:
            A_options = ["顯示", "管理實體別名"]
            A_selected_option = st.sidebar.radio("選擇一個功能", A_options)

            if A_selected_option == "管理實體別名":
                st.write("只有屬於同一實體類別的實體實例可以創建別名， 且每個實體實例至多歸屬一個別名。")
                if MULTIPLE_FILE:
                    st.write("該功能僅應用於當前文件。")

                AliasName = st.text_input("請輸入實體別名的名稱（名稱必須是唯一的）：")

                boxOptions = [""]
                for c in instance_by_class.keys():
                    if len(instance_by_class[c]) != 0:
                        boxOptions.append(ALL_NER_TAG[c] + "|" + c)
                AliasClass = st.sidebar.selectbox("選擇一個實體類別", boxOptions)
                if AliasClass:
                    AliasClass = AliasClass.split("|")[1]

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("創建"):
                        addAlias(AliasName, AliasClass)
                with col2:
                    if st.button("刪除"):
                        delAlias(AliasName)
                    

                aliasToManage = st.selectbox("選擇要管理的實體別名", list(instance_by_alias.keys()), None)

                if aliasToManage in instance_by_alias:

                    A_Class = instance_by_alias[aliasToManage][0]
                    avaiEntities = instance_by_class[A_Class]
                    avaiEntities = availForAlias(avaiEntities.copy(), aliasToManage)
                    defaultGMember = instance_by_alias[aliasToManage][1]
                    alias_members = st.multiselect("修改成員", avaiEntities, defaultGMember)
                    manageAlias(aliasToManage, alias_members)

                    Display_inst = instance_by_alias[aliasToManage][1]
                    session_state["Display_inst"] = Display_inst
                else:
                    Display_inst = []
                    session_state["Display_inst"] = Display_inst

            if A_selected_option == "顯示":
                selected_alias = st.selectbox("選擇實體別名", list(instance_by_alias.keys()))
                if selected_alias in instance_by_alias:

                    Display_inst = instance_by_alias[selected_alias][1]
                    session_state["Display_inst"] = Display_inst

                    DisplayList = []
                    for m in instance_by_alias[selected_alias][1]:
                        instanceTOList(m, DisplayList)

                    if ByFreq:
                        DisplayList = DisplayListByFreq(DisplayList.copy(), True)
                    DisplayList = [key for key in DisplayList if key in list(set(DisplayList))]
                    for inst in DisplayList:
                        freq = instance_displayName[inst][0]
                        if instance_displayName[inst][1] != ():
                            A_name = instance_displayName[inst][1][0]
                            A_freq = instance_displayName[inst][1][1]
                            st.button(f"{inst}|{A_name} ({freq}|{A_freq} 次)")
                        else:
                            st.button(f"{inst} ({freq} 次)")
                else:
                    st.write("暫無數據，請先標注實體實例。")
                    Display_inst = []
                    session_state["Display_inst"] = Display_inst


# display text with annotation on the main page
st.markdown("#")
DisplayNERAnnotation(instances, text, Display_inst)
st.markdown("#")

# store data in "operator" global variables 
StoreData(CurrentFile)


#########################################################################################################################################
#########################################################################################################################################
# session 3: data summary and visualization
if Display_inst:

    st.markdown("---")
    st.subheader("• " + "數據展示")

    tab1, tab2, tab3, tab4= st.tabs(["實體總數概覽 (Overview)", "實體頻率圖 (Bar chart)", "實體位置散佈圖 (Scatter plot)", "實體頻率趨勢圖 (Line chart)"])

    with tab1:
        # visualization - NER boxes
        ###############################################################
        # function: DrawNERBox()
        # need data: instance_by_class,  ALL_NER_TAG_Color, ALL_NER_TAG
        # author: Sherry
        ###############################################################
        def DrawNERBox():
            reorder = []
            for c in instance_by_class:
                if not c or c not in ALL_NER_TAG:
                    continue
                # if len(instance_by_class[c]) == 0:
                #     continue
                reorder.append((c, len(instance_by_class[c])))
            reorder = sorted(reorder, key=lambda x: x[1], reverse=True)
            perRow = 4
            box_width = "140px"
            box_height = "85px"
            i = 0
            cols = st.columns(perRow)
            for c, l in reorder:
                box_color = ALL_NER_TAG_Color[c]
                box_style = f"background-color: {box_color}; padding: 10px; margin-right: 10px; margin-bottom: 10px; width: {box_width}; height: {box_height};"
                freqPart = f"<span style='font-weight: bold; font-size: 25px;'>{l}</span>"
                tagPart = ALL_NER_TAG[c] + " | " + c
                boxtext = f"<span style='font-size: 13px;'>{freqPart} {tagPart}</span>"
                cols[i % perRow].markdown(f"<div style='{box_style}'>{boxtext}</div>", unsafe_allow_html=True)
                i += 1

        # display
        DrawNERBox()


    with tab2:
        # visualization - frequency bar chart
        ###############################################################
        # function: FreqBarChart(Display_inst.copy())
        # frequency chart of current displayed instances
        # need data: instance_displayName
        # author: Sherry
        ###############################################################
        def FreqBarChart(Display_inst, ApplyAlias_barChart):

            if not Display_inst:
                return

            ChartData = {}
            for inst in Display_inst:
                if instance_displayName[inst][1] and ApplyAlias_barChart:
                    ChartData[inst] = instance_displayName[inst][1][1]
                else:
                    ChartData[inst] = instance_displayName[inst][0]

            ChartData = pd.DataFrame.from_dict(ChartData, orient='index', columns=['頻率'])
            ChartData = ChartData.sort_values(by='頻率', ascending=False)
            if ChartData.shape[0] > 15:
                st.write("實體實例太多，僅顯示頻率最高的15個。")
                ChartData = ChartData.head(15)

            # Create the horizontal bar chart
            fig = px.bar(
                ChartData,
                x='頻率',
                y=ChartData.index,
                orientation='h'
            )

            fig.update_layout(
                title='實體實例的頻率',
                xaxis_title='頻率',
                yaxis_title='實體實例',
                yaxis=dict(autorange="reversed")
            )

            # Set the background color for the plot area
            fig.update_layout(
            plot_bgcolor='rgba(230, 245, 255, 1)',  
            paper_bgcolor='rgba(230, 245, 255, 1)',
            margin=dict(l=50, r=20, b=20)  
            )

            st.plotly_chart(fig)


        ###############################################################
        # display frequency bar chart
        # author: Sherry
        ###############################################################
        if Display_inst:
            st.subheader("實體實例的頻率條形圖")
            ApplyAlias_barChart = st.checkbox("將實體別名應用於頻率條形圖")
            st.write("若要使用實體別名的總頻率作為實例的頻率，請點選該方塊。")
            FreqBarChart(Display_inst.copy(), ApplyAlias_barChart)


    with tab3:
        ###############################################################
        # visualization - appearence position graph

        ###############################################################
        # function: word_positions(word, text)
        # return the list of all the position indexes of a word in a piece of text
        # parametner word: string
        #            text: string
        # author: Sherry
        ###############################################################
        def word_positions(word, text):
            pattern = re.compile(word)
            positions = [match.start() for match in pattern.finditer(text)]
            return positions

        ###############################################################
        # function: EntityPositionsPlot(word_indexes)
        # parametner: word_indexes : dictionary
        # author: Sherry
        ###############################################################
        def EntityPositionsPlot(word_indexes):
            fig = go.Figure()

            for word, indexes in word_indexes.items():
                fig.add_trace(
                    go.Scatter(
                        x=indexes,
                        y=[word] * len(indexes),
                        mode='markers',
                        marker=dict(
                            size=10,
                            color='blue' 
                        ),
                        showlegend=False 
                    )
                )

            fig.update_layout(
                title='實體實例的位置散佈圖',
                xaxis=dict(title='實體實例在文章中出現的位置（字）'),
                yaxis=dict(title='實體實例'),
                showlegend=True
            )

            # Set the background color for the plot area
            fig.update_layout(
            plot_bgcolor='rgba(230, 245, 255, 1)',  
            paper_bgcolor='rgba(230, 245, 255, 1)',
            margin=dict(l=50, r=20, b=20)  
            )

            return fig

        ###############################################################
        # display scatter plot of Entity Occurrences
        # author: Sherry
        ###############################################################
        if Display_inst:
            st.subheader('實體實例出現位置的一維散佈圖')

            # selected_list = st.multiselect("Select the entities you want to view: ", Display_inst, Display_inst[:15])

            entity_indexes = {}
            for e in Display_inst:
                entity_indexes[e] = word_positions(e, text)
            
            entity_indexes = dict(sorted(entity_indexes.items(), key=lambda x: len(x[1]), reverse=True))
            entity_indexes = collections.OrderedDict(entity_indexes)
            if len(entity_indexes) > 15:
                st.write("實體實例太多，僅顯示頻率最高的15個。")
                entity_indexes = dict(list(entity_indexes.items())[:15])


            fig = EntityPositionsPlot(entity_indexes)
            fig.update_layout(yaxis=dict(autorange="reversed"))

            st.plotly_chart(fig, use_container_width=True)


    with tab4:
        ###############################################################
        # visualization - frequency trend graph

        ###############################################################
        # function: DataForTrend()
        # return the data for trend as a list, format: [("inst", freq), ...]
        # use data in instances, and instance_displayName
        # author: Sherry
        ###############################################################
        def DataForTrend(Display_inst, instance_displayName, ApplyAlias_trend):
            TrendData = []
            for inst in Display_inst:
                freq = 0
                if inst in instance_displayName:
                    freq = instance_displayName[inst][0]
                    if instance_displayName[inst][1] and ApplyAlias_trend:
                        freq = instance_displayName[inst][1][1]
                thisdata = (inst, freq)
                TrendData.append(thisdata)
            return TrendData

        ###############################################################
        # display trend graph
        # author: Berry
        ###############################################################
        if Display_inst:
            st.subheader("實體實例在各文件中頻率的趨勢圖")
        
            if len(FILES_WORKON) > 1:
                ApplyAlias_trend = st.checkbox("將實體別名應用於頻率趨勢圖")
                st.write("若要使用實體別名的總頻率作為實例的頻率，請點選該方塊。")
                dict_files = {}
                for file in FILES_WORKON:
                    dict_files[file] = DataForTrend(Display_inst.copy(), session_state["all_files"][file]["instance_displayName"].copy(), ApplyAlias_trend)
                
                # get different item[0]
                all_items = set()
                for instances in dict_files.values():
                    all_items.update(item[0] for item in instances)

                selected_item = st.selectbox("選擇一個詞語", list(all_items))

                # draw gragh
                data = {}
                x_values = []
                y_values = []
                for file_name, instances in dict_files.items():
                    x_values.append(file_name)
                    y_value = next((item[1] for item in instances if item[0] == selected_item), 0)
                    y_values.append(y_value)

                data["文件"] = x_values
                data["頻率"] = y_values

                df = pd.DataFrame(data)
                fig = px.line(df, x="文件", y="頻率")
                fig.update_layout(title="實體實例的頻率趨勢圖")

                # interger y-axis
                y_min = np.floor(min(y_values))
                y_max = np.ceil(max(y_values))
                y_ticks = np.arange(y_min, y_max + 1, 1)
                fig.update_yaxes(tickvals=y_ticks, tickformat=".0f")

                # Set the background color for the plot area
                fig.update_layout(
                plot_bgcolor='rgba(230, 245, 255, 1)',  
                paper_bgcolor='rgba(230, 245, 255, 1)'  
                )

                st.plotly_chart(fig)
            else:
                st.write("僅適用於多個文件。")
