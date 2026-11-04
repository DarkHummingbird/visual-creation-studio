"""Actual billing extension point. No provider billing API or fabricated settlement."""
from typing import Protocol
from decimal import Decimal
class CostBackend(Protocol):
    def actual_cost(self,attempt_id:str)->Decimal|None:...
class UnconnectedCosts:
    def actual_cost(self,attempt_id:str)->None:return None
    def status(self):return {'implemented':False,'actual':None,'status':'NOT_IMPLEMENTED'}
cost_backend=UnconnectedCosts()
