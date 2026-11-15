"""Session-local evidence references and checked arithmetic for dependent tool steps."""
import copy
import math


class EvidenceLedger:
    def __init__(self, capacity=64):
        self.capacity, self.next_id, self.entries = capacity, 1, {}

    def add(self, tool, payload, arguments=None):
        result=copy.deepcopy(payload)
        evidence_id=f'E{self.next_id}'
        self.next_id+=1
        result['evidence_id']=evidence_id
        self.entries[evidence_id]={'tool':tool,'arguments':copy.deepcopy(arguments or {}),'result':copy.deepcopy(result)}
        while len(self.entries)>self.capacity:
            self.entries.pop(next(iter(self.entries)))
        return result

    def compare(self,left_id,right_id,operation):
        try:
            left=self.entries[left_id]['result']['data']
            right=self.entries[right_id]['result']['data']
        except KeyError:
            return {'ok':False,'error':{'code':'unknown_evidence','message':'Use IDs returned by successful tools in this session; repeat the source queries if expired.','retryable':False}}
        def scalar(data):
            if 'risk_probability' in data:
                return data['risk_probability'],'fraction'
            unit=data.get('unit')
            if not unit:
                unit='years' if data.get('column')=='age' else 'score:'+str(data.get('column'))
            return data.get('value'),unit
        a,au=scalar(left);b,bu=scalar(right)
        numeric=lambda x:isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)
        if not numeric(a) or not numeric(b) or au!=bu or left.get('model')!=right.get('model'):
            return {'ok':False,'error':{'code':'incompatible_evidence','message':'Both references must contain finite scalars with matching units/outcomes.','retryable':False}}
        if operation in ('ratio','relative_change') and b==0:
            return {'ok':False,'error':{'code':'zero_denominator','message':'Cannot divide by a zero reference. Report the counts or choose a difference.','retryable':False}}
        operations={'difference':lambda:a-b,'ratio':lambda:a/b,'relative_change':lambda:(a-b)/b}
        if operation not in operations:
            return {'ok':False,'error':{'code':'invalid_operation','message':'Supported operations: difference, ratio, relative_change.','retryable':False}}
        value=operations[operation]()
        return {'ok':True,'source':'Deterministic arithmetic over session evidence',
                'data':{'value':value,'unit':au if operation=='difference' else 'ratio',
                        'operation':operation,'left_id':left_id,'right_id':right_id,'left_value':a,'right_value':b},
                'parents':[left_id,right_id]}
