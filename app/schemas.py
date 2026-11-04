from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schemaVersion:Literal[1]=1
class Scene(Contract):
    title:str=Field(min_length=1,max_length=150)
    location:str
    time:str
    action:str
    dialogue:str=''
class Script(Contract):
    title:str
    synopsis:str
    scenes:list[Scene]=Field(min_length=1,max_length=200)
    warnings:list[str]=[]
class Card(Contract):
    id:str=Field(min_length=1)
    kind:Literal['CHARACTER','LOCATION','PROP']
    name:str
    description:str
    voice:str=''
    characterId:str=''
    lookVersionId:str=''
    assetId:str=''
class Cards(Contract):
    cards:list[Card]=Field(max_length=60)
    warnings:list[str]=[]
class Shot(Contract):
    id:str
    title:str
    prompt:str=Field(min_length=1)
    action:str
    dialogue:str=''
    speakerId:str=''
    camera:str
    seconds:int=Field(ge=2,le=30)
    referenceIds:list[str]=Field(max_length=3)
    startState:str=''
    endState:str=''
    dependsOn:list[str]=[]
class Shots(Contract):
    shots:list[Shot]=Field(min_length=1,max_length=80)
    warnings:list[str]=[]
class NewDraft(BaseModel):
    scene:Literal['ecommerce','drama']
    name:str=Field(min_length=1,max_length=100)
class SaveDraft(BaseModel):
    baseVersion:int
    mutationId:str=Field(min_length=8,max_length=100)
    data:dict
class StartRun(BaseModel):
    kind:Literal['script','cards','shots','references','frames','videos','compose','oneclick','ecommerce','editimage']
    mutationId:str=Field(min_length=8,max_length=100)
    baseVersion:int
    paidConsent:bool=False
    selectedIds:list[str]=[]
    options:dict={}
