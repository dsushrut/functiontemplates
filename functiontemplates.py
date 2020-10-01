#Copyright 2019-2020 VMware, Inc.
#SPDX-License-Identifier: MIT
import traceback, sys, inspect
from pprint import pprint, pformat
from time import sleep, time, strftime, localtime
from multiprocessing.pool import ThreadPool as Pool
import random
from copy import deepcopy
import logging
lgr = logging.getLogger('functiontemplate')
lgr.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
lgr.addHandler(ch)


def temp_print_msg_box(msg, indent=1, width=None, title=""):
    lines = msg.split('\n')
    space = " " * indent
    if not width:
        width = max(map(len, lines)+[len(title)])
    box = '+'+"=" * (width + indent * 2)+'+\n'
    if title:
        box += '|'+space+title+ " " * (width-len(title))+space+'|\n'  # title
        box += '|'+space+"-" * (len(title))+ " " * (width-len(title))+space+'|\n'  # underscore
    box += ''.join(['|'+space+line+" " * (width-len(line))+space+'|\n' for line in lines])
    box += '+'+"=" *(width + indent * 2)+'+'  # lower_border
    return "\n"+box

def box_log(msgi,**kwargs):
    lgr.debug("\n"+temp_print_msg_box(msg,**kwargs))

box_log = temp_print_msg_box

def checkexception(output,recursepath=None):
    #lgr.debug(box_log(" Checking exception for output:\n%s"% pformat(output)))
    if recursepath==None:
        lgr.debug(box_log(" Checking exception for output:\n%s"% pformat(output)))
        recursepath=set()
    if id(output) in recursepath:
        return
    else:
        recursepath.add(id(output))
    if isinstance(output,dict):
        if 'hadexception' in output:
            return output['hadexception']
        o=[checkexception(value,recursepath=recursepath) for value in output.values()]
        o=[one for one in o if one !=None]
        if o:
            return o[0]
    elif isinstance(output,list) or isinstance(output, tuple):
        o=[checkexception(value,recursepath=recursepath) for value in output]
        o=[one for one in o if one !=None]
        if o:
            return o[0]

def resolver_(resolvestring, outputdict):
    resolvelist=resolvestring.split(".")
    resolvelist=resolvelist[1:]
    output=outputdict
    for onestring in resolvelist:
        if onestring!='':
            if onestring.endswith("]"):
                temp=onestring.split("[")
                index=int(temp[1].split("]")[0])
                key=temp[0]
                output=output[key][index]
            else:
                output=output[onestring]
    return output

def resolve_args_kwargs(localdict, args, kwargs, globaldict={}):
    output_args=[]
    output_kwargs={}
    for arg in args:
        if isinstance(arg,str):
            if arg.startswith("getresult."):
                try:
                    output_args.append(resolver_(arg,localdict))
                except Exception as e:
                    output_args.append(resolver_(arg,globaldict))
            else:
                output_args.append(arg)
        else:
            output_args.append(arg)
    for key in kwargs.keys():
        output_kwargs[key] = kwargs[key]
        if isinstance(kwargs[key],str):
            if kwargs[key].startswith("getresult."):
                try:
                    output_kwargs[key] = resolver_(kwargs[key],localdict)
                except Exception as e:
                    output_kwargs[key] = resolver_(kwargs[key],globaldict)
    return (output_args,output_kwargs)

def resolve_exec(fundamentalfunction,localdict, globaldict={}):
    def internalfunction(*args,**kwargs):
        evaluated_args, evaluated_kwargs = resolve_args_kwargs(localdict,args,kwargs, globaldict=globaldict)
        return fundamentalfunction(*evaluated_args,**evaluated_kwargs)
    internalfunction.__name__=fundamentalfunction.__name__
    return internalfunction

def time_log_deco(fundamentalfunction, outputdict):
    def internalfunction(*args,**kwargs):
        outputdict['starttime']=time()
        #outputdict['ignoreexception']=ignoreexception
        outputdict['h_start']=strftime('%Y-%m-%d %H:%M:%S', localtime(outputdict['starttime']))
        outputdict['run_id']=str(random.random()).split(".")[-1]
        lgr.debug("##### start run_id:%s" % outputdict['run_id'])
        output=fundamentalfunction(*args,**kwargs)
        outputdict['endtime'] = time()
        outputdict['timetaken'] = outputdict['endtime']-outputdict['starttime']
        outputdict['h_end']=strftime('%Y-%m-%d %H:%M:%S', localtime(outputdict['endtime']))
        lgr.debug("##### end run_id:%s" % outputdict['run_id'])
        return output
    internalfunction.__name__=fundamentalfunction.__name__
    return internalfunction

def resolve_time_deco(fundamentalfunction,outputdict,localdict,  globaldict={}):
    resolvedfunction=resolve_exec(fundamentalfunction,localdict,globaldict=globaldict)
    return time_log_deco(resolvedfunction,outputdict)

def exceptiondecorator(fundamentalfunction,outputdict,localdict,ignoreexception,exceptionhandler, outputcopy=True, globaldict={}):
    def internalfunction(*args,**kwargs):
        try:
            output=resolve_exec(fundamentalfunction,localdict, globaldict=globaldict)(*args,**kwargs)
            if outputcopy:
                outputdict['output']=output
        except Exception as e:
            exc_type, exc_value, tb = sys.exc_info()
            exceptiondict={"ignoreexception":ignoreexception}
            exceptiondict['msg']=str(e)
            exceptiondict['exception']=e
            localdict['exception']=e
            exceptiondict['traceback']=[]
            tblast=tb
            limitlines = 50
            for line in traceback.extract_tb(tb):
                limitlines=limitlines-1
                if limitlines==0:
                    break
                context_variables = tblast.tb_frame.f_locals
                if 'functiontemplate.py' not in str(line) and 'testrunner.py' not in str(line):
                    exceptiondict['traceback'].append({'line':line})
                else:
                    exceptiondict['traceback'].append({'line':line})
                tblast=tblast.tb_next
            outputdict['hadexception']=[exceptiondict]
            outputdict['output']=str(e)
            lgr.debug(box_log(pformat(outputdict)))
            if exceptionhandler:
                outputdict['exceptionhandler_output']={}
                resolved_exception_handler=exceptiondecorator(exceptionhandler['function'],outputdict['exceptionhandler_output'],localdict,ignoreexception,None, globaldict=globaldict)
                o=resolved_exception_handler(*exceptionhandler['args'],**exceptionhandler['kwargs'])
            outputdict['output']=str(e)
            output=str(e)
        return output
    internalfunction.__name__=fundamentalfunction.__name__
    return time_log_deco(internalfunction,outputdict)

def applydecos(fundamental_function, decolist,localdict=None, outputdict={}, globaldict={}):
    """ wraps the fundamental function with the given decorator list
        If decorator takes variables then decorator must be a dictionary with following keys:
        function = actual decorator function
        args = arguments to be passed to the decorator function
        kwargs = keyword arguments to be passed to the decorator function
    """
    msg=[]
    msg.append("decolist = %s" % pformat(decolist))
    msg.append("outputdict = %s" % pformat(outputdict))
    msg.append("localdict = %s" % pformat(localdict))
    msg.append("fundamental_function = %s" % fundamental_function.__name__)
    lgr.debug(box_log("\n".join(msg)))
    if localdict == None:
        localdict=outputdict

    finalfunction = {'f': fundamental_function}
    def internalfunction(*args, **kwargs):
        #print(decolist)
        msg = []
        msg.append("decolist = %s" % pformat(decolist))
        msg.append("outputdict = %s" % pformat(outputdict))
        finalmsg = temp_print_msg_box("\n".join(msg), title="inside internalfunction of applydecos")
        lgr.debug("\n"+finalmsg)
        int_decolist=decolist
        if callable(decolist):
            int_decolist=[decolist]
        for deco in int_decolist:
            if callable(deco):
                finalfunction['f'] = deco(finalfunction['f'])
            else:
                evaluateddeco_args, evaluatedeco_kwargs = resolve_args_kwargs(localdict,
                                                                              deco['args'], deco['kwargs'], globaldict=globaldict)
                finalfunction['f'] = deco['function'](finalfunction['f'], *evaluateddeco_args, **evaluatedeco_kwargs)
                finalfunction['f'].__name__=fundamental_function.__name__

        return finalfunction['f'](*args, **kwargs)
    internalfunction.__name__=fundamental_function.__name__
    return internalfunction


def runfunctionlist(functionlist,localdict,outputdict, parallel=False, ignoreexception=False,exceptionhandler=None, globaldict={}):
    """ Executes list of functions.
        If function takes variables then element of functionlist has to be dictionary
        with following keys:
        function = actual decorator function
        args = arguments to be passed to the decorator function
        kwargs = keyword arguments to be passed to the decorator function
    """
    outputdict['output']=[]
    def onefunctionhandler(f):
        output={}
        def functionforexception():
            lgr.debug(box_log(pformat(f), title="onefunctionhanlder-functionforexception"))
            if callable(f):
                output['name']=f.__name__
                output['output'] = f()
            else:
                #output = {}
                def dummy_function(*args,**kwargs):
                    if isinstance(f['function'], functiontemplate) or isinstance(f['function'], functiongroup):
                        return f['function'].run(*args,**kwargs)
                    return f['function'](*args,**kwargs)
                output['name']=f.get('name',f['function'].__name__)
                dummy_function.__name__=output['name']
                if 'condition' in f:
                    if isinstance(f['condition'],bool):
                        if not f['condition']:
                            lgr.debug("condition false for %s" % pformat(f))
                            return
                    elif f['condition']:
                        if isinstance(f['condition']['function'],str):
                            if not resolver_(f['condition']['function'], localdict):
                                lgr.debug("condition false for %s" % pformat(f))
                                return
                        elif isinstance(f['condition']['function'],bool):
                            if not f['condition']['function']:
                                lgr.debug("condition false for %s" % pformat(f))
                                return
                        else:
                            evaluatedcondition_args, evaluatedcondition_kwargs = resolve_args_kwargs(localdict,
                                    f['condition']['args'], f['condition']['kwargs'], globaldict=globaldict)
                            output['conditionoutput'] = f['condition']['function'](*evaluatedcondition_args,
                                     **evaluatedcondition_kwargs)
                            if not output['conditionoutput']:
                                lgr.debug("condition false for %s" %  pformat(f))
                                return
                evaluated_args, evaluated_kwargs = resolve_args_kwargs(localdict,
                        f['args'], f['kwargs'], globaldict=globaldict)
                if 'template' in f:
                    if f['template']:
                        if not isinstance(f['template'],list):
                            f['template'] = [f['template']]
                        finalfunction= dummy_function
                        name = output['name']
                        for onetemplate in f['template']:
                            if callable(onetemplate):
                                onetemplate= {"function":onetemplate,
                                        "args":[], "kwargs":{}}
                            onetemplate_args=onetemplate.get("args",[])
                            onetemplate_kwargs=onetemplate.get('kwargs',{k:v for k,v in onetemplate.items() if k not in ['args','kwargs','function']})
                            evaluatedtemplate_args, evaluatedtemplate_kwargs = resolve_args_kwargs(localdict,
                                    onetemplate_args, onetemplate_kwargs,globaldict=globaldict)
                            temp_output={'starttime':time(), 'ignoreexception':f.get('ignoreexception',ignoreexception)}
                            if isinstance(onetemplate['function'], functiontemplate) or isinstance(onetemplate['function'], functiongroup):
                                finalfunction = onetemplate['function'](finalfunction,*evaluatedtemplate_args,
                                    name=name,outputdict=temp_output,localdict=None,globaldict=globaldict,
                                    ignoreexception=f.get('ignoreexception', ignoreexception),
                                    exceptionhandler=f.get('exceptionhandler',exceptionhandler),
                                    **evaluatedtemplate_kwargs)
                            else:
                                finalfunction = onetemplate['function'](finalfunction,*evaluatedtemplate_args,
                                        **evaluatedtemplate_kwargs)
                            finalfunction.__name__=name
                        output['output'] = exceptiondecorator(finalfunction,
                                output,localdict,f.get('ignoreexception', ignoreexception),f.get('exceptionhandler',exceptionhandler),globaldict=globaldict)(*f['args'],**f['kwargs'])
                    else:
                        output['output'] = exceptiondecorator(dummy_function,
                                output,localdict,f.get('ignoreexception', ignoreexception),f.get('exceptionhandler',exceptionhandler), globaldict=globaldict)(*f['args'],**f['kwargs'])
                else:
                    output['output'] = exceptiondecorator(dummy_function,
                            output,localdict,f.get('ignoreexception', ignoreexception),f.get('exceptionhandler',exceptionhandler),globaldict=globaldict)(*f['args'],**f['kwargs'])
        functionforexception()
        return output
    result=None
    if parallel:
        #lgr.debug("########################## parallel $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$44")
        pool=Pool(processes=len(functionlist))
        result = pool.map(onefunctionhandler, functionlist)
        pool.close()

    for n in range(len(functionlist)):
        oneoutput=None
        f=functionlist[n]
        if parallel:
            oneoutput=result[n]
        else:
            oneoutput=onefunctionhandler(f)
        outputdict['output'].append(oneoutput)

        if checkexception(oneoutput) and not f.get('ignoreexception',False) and not parallel:
            break
    lgr.debug("outputdict:"+box_log(pformat(outputdict), title="runfunctionlist end"))
    return outputdict

def deco_of_runfunctionlist(functionlist,localdict,outputdict,name='default',parallel=False, ignoreexception=False, exceptionhandler=None,globaldict={}):
    def internalfunction(*args,**kwargs):
        return runfunctionlist(functionlist,localdict,outputdict,parallel=parallel, ignoreexception=ignoreexception, exceptionhandler=exceptionhandler,globaldict=globaldict)
    internalfunction.__name__=name+"-decoOfRunfunctionlist"
    return internalfunction

class functiongroup(object):
    def __init__(self,name = "default", **kwargs):
        self.__name__=name
        self.name=name
        self.data=kwargs
        self.data['self']=self
        self.functionlist=[]
        self.nametofunctiondict={}
        self.decoratorlist=[]
        self.ignoreexception=False
        self.exceptionhandler=None
        self.parallel=False
        self.sequence=None
        self.defaultcondition_handler=None
        self.defaulttemplate=None
        self.results=[]
        self.resolvedict={}
    def clone(self,*args,**kwargs):
        myclone = deepcopy(self)
        name = kwargs.pop("name",self.name)
        myclone.name=name
        myclone.data['self']=myclone
        myclone.data.update(**kwargs)
        return myclone
    def adddecorator(self, taskfunction, *args, **kwargs):
        internal_conditionhandler=self.defaultcondition_handler
        if 'condition' in kwargs:
            internal_conditionhandler = {'function':kwargs.pop('condition'),
                    'args': kwargs.pop('conditionargs',[]),
                    'kwargs': kwargs.pop('conditionkwargs',{})}
        taskdata={'function': taskfunction,
            'args':args,'kwargs': kwargs,
            'condition':internal_conditionhandler}
        self.decoratorlist.append(taskdata)
    def get_function_names(self):
        return [x['name'] for x in self.functionlist]
    def internal_gettaskdata(self, taskfunction,
            internal_template, internal_exceptionhandler,
            internal_conditionhandler, *args, **kwargs):
        name = kwargs.pop('name', taskfunction.__name__)
        if 'template' in kwargs:
            temp_template = kwargs.pop('template')
            if isinstance(temp_template,list):
                internal_template=temp_template
            else:
                internal_template = [{'function':temp_template,
                    'args': kwargs.pop('templateargs',[]),
                    'kwargs': kwargs.pop('templatekwargs',{})}]
        if 'condition' in kwargs:
            internal_conditionhandler = {'function':kwargs.pop('condition'),
                    'args': kwargs.pop('conditionargs',[]),
                    'kwargs': kwargs.pop('conditionkwargs',{})}
        ignoreexception= kwargs.pop('ignoreexception',None)
        if 'exceptionhandler' in kwargs:
            internal_exceptionhandler = {'function': kwargs.pop('exceptionhandler'),
                    'args': kwargs.pop('exceptionargs',[]),
                    'kwargs': kwargs.pop('exceptionkwargs',{})}
        taskdata={'function': taskfunction,
            'args':args,'kwargs': kwargs, 'name':name,
            'condition':internal_conditionhandler,
            'template':internal_template}
        if ignoreexception!=None:
            taskdata['ignoreexception']=ignoreexception
        #if exceptionhandler!=None:
        taskdata['exceptionhandler'] =  internal_exceptionhandler
        return taskdata
    def internal_addfunction(self, taskfunction,
            internal_template, internal_exceptionhandler,
            internal_conditionhandler, *args, **kwargs):
        self.functionlist.append(self.internal_gettaskdata(taskfunction,
            internal_template, internal_exceptionhandler,
            internal_conditionhandler, *args, **kwargs))
        self.nametofunctiondict[self.functionlist[-1]['name']]=self.functionlist[-1]
    def add(self, taskfunction,
            *args, **kwargs):
        self.internal_addfunction(taskfunction,
            self.defaulttemplate, self.exceptionhandler,
            self.defaultcondition_handler, *args, **kwargs)
    def getand(self):
        pass
    def getor(self):
        pass
    def __call__(self,taskfunction,localdict=None,outputdict=None, parallel=None, ignoreexception=None,exceptionhandler=None,globaldict=None,sequence=None,
            randomize=None, **kwargs):
        if ignoreexception==None:
            ignoreexception=self.ignoreexception
        if parallel==None:
            parallel=self.parallel
        if outputdict==None:
            outputdict={}
        self.results.append(outputdict)
        if localdict==None:
            localdict=outputdict
        if 'data' not in localdict:
            localdict['data']={}
        localdict['data'].update(self.data)
        localdict['data'].update(kwargs)
        if globaldict==None:
            globaldict=localdict
        functionlist=self.functionlist[:]
        if sequence:
            functionlist=[self.nametofunctiondict[x] for x in sequence]
        if randomize:
            functionlist=random.sample(functionlist,len(functionlist))
        outputcopy=True
        if not taskfunction:
            taskfunction = deco_of_runfunctionlist(functionlist, localdict, name=self.name, outputdict=outputdict,
                    parallel=parallel,ignoreexception=ignoreexception, exceptionhandler=exceptionhandler,globaldict=globaldict)
            outputcopy=False
        decorated_function = exceptiondecorator(applydecos(taskfunction, self.decoratorlist,localdict=localdict, outputdict=outputdict, globaldict=globaldict),
                outputdict, localdict, ignoreexception, exceptionhandler, outputcopy=outputcopy, globaldict=globaldict)
        decorated_function.__name__=self.name+taskfunction.__name__
        return decorated_function
    def run(self,localdict=None,outputdict=None, parallel=None, ignoreexception=None,exceptionhandler=None,globaldict=None, **kwargs):
        if outputdict==None:
            outputdict={}
        if localdict==None:
            localdict=outputdict
        if 'data' not in localdict:
            localdict['data']={}
        localdict['data'].update(self.data)
        localdict['data'].update(kwargs)
        if globaldict==None:
            globaldict=localdict
        temp_output = self.__call__(None,localdict=localdict,outputdict=outputdict, parallel=parallel,globaldict=globaldict,
                              ignoreexception=ignoreexception,exceptionhandler=exceptionhandler, **kwargs)()
        return outputdict



class decoratorgroup(object):
    def __init__(self, name="default"):
        self.decoratorlist=[]
        self.ignoreexception=False
        self.name = name
        self.exceptionhandler=None
        self.defaultconditionhandler=None
        self.resolvedict={}
    def adddecorator(self, taskfunction, *args, **kwargs):
        internal_conditionhandler=self.defaultconditionhandler
        if 'condition' in kwargs:
            internal_conditionhandler = {'function':kwargs.pop('condition'),
                    'args': kwargs.pop('conditionargs',[]),
                    'kwargs': kwargs.pop('conditionkwargs',{})}
        taskdata={'function': taskfunction,
            'args':args,'kwargs': kwargs,
            'condition':internal_conditionhandler}
        self.decoratorlist.append(taskdata)
    def run(self, taskfunction, outputdict=None, resolvedict=None, ignoreexception=None, exceptionhandler=None, **kwargs):
        msg = []
        msg.append("taskfunction %s" % pformat(taskfunction))
        msg.append("resolvedict = %s" % pformat(resolvedict))
        msg.append("outputdict = %s" % pformat(outputdict))
        msg.append("self.decoratorlist = %s" % pformat(self.decoratorlist))
        #msg.append("stack = %s" % pformat(inspect.stack()))
        finalmsg = temp_print_msg_box("\n".join(msg), title="decoratorgroup:run")
        lgr.debug("\n"+finalmsg)
        #importpdb; pdb.set_trace();
        if outputdict==None:
            outputdict={}
        if ignoreexception==None:
            ignoreexception=self.ignoreexception
        if exceptionhandler==None:
            exceptionhandler=self.exceptionhandler
        if resolvedict==None:
            resolvedict=self.resolvedict
        if 'data' not in resolvedict:
            resolvedict['data']={}
        resolvedict['data'].update(kwargs)
        #return applydecos(taskfunction, self.decoratorlist, outputdict=resolvedict)
        decorated_function = exceptiondecorator(applydecos(taskfunction, self.decoratorlist,resolvedict=resolvedict, outputdict=outputdict),
                outputdict, resolvedict, ignoreexception, exceptionhandler)
        decorated_function.__name__=self.name+"-decoratorgroup"
        return decorated_function
        #return outputdict
    def __call__(self,*args, **kwargs):
        return self.run(*args,**kwargs)


class functiontemplate(functiongroup):
    def __init__(self,*args, **kwargs):
        functiongroup.__init__(self,*args,**kwargs)
        self.prefunctions = functiongroup(name = self.name+"-prefunctions")
        self.tasks = functiongroup(name = self.name+"-tasks")
        self.postfunctions = functiongroup(name = self.name+"-postfunctions")
        self.data['ft_self']=self
    def update_data(self,*args,**kwargs):
        self.data.update(**kwargs)
    def __call__(self,taskfunction,localdict=None,outputdict=None, parallel=None, ignoreexception=None,exceptionhandler=None,globaldict=None,
            sequence=None, randomize=None, **kwargs):
        if outputdict==None:
            outputdict={}
        self.results.append(outputdict)
        if localdict==None:
            localdict=outputdict
        if 'data' not in localdict:
            localdict['data']={}
        localdict['data'].update(self.data)
        localdict['data'].update(kwargs)
        if globaldict==None:
            globaldict=localdict
        def prepost(*args,**kwargs):
            outputdict['001-prefunctions']={}
            temp_output=self.prefunctions.run(localdict=localdict,outputdict=outputdict['001-prefunctions'], globaldict=globaldict,
                    ignoreexception=ignoreexception,exceptionhandler=exceptionhandler)
            problems = checkexception(outputdict['001-prefunctions'])
            if problems:
                if not problems[0].get('ignoreexception', ignoreexception):
                    return outputdict
            outputdict['002-centraltasks']={}
            temp_output=self.tasks(taskfunction,localdict=localdict,outputdict=outputdict['002-centraltasks'], parallel=parallel,globaldict=globaldict,
                    sequence=sequence,randomize=randomize,
                    ignoreexception=ignoreexception,exceptionhandler=exceptionhandler, **kwargs)(*args,**kwargs)
            problems = checkexception(outputdict['002-centraltasks'])
            if problems:
                if not problems[0].get('ignoreexception', ignoreexception):
                    return outputdict
            outputdict['003-postfunctions']={}
            temp_output=self.postfunctions.run(localdict=localdict,outputdict=outputdict['003-postfunctions'],globaldict=globaldict,
                    ignoreexception=ignoreexception,exceptionhandler=exceptionhandler)
            return outputdict
        if taskfunction:
            prepost.__name__ = taskfunction.__name__
        else:
            prepost.__name__ = self.name
        decorated_function = exceptiondecorator(applydecos(prepost, self.decoratorlist,localdict=localdict, outputdict=outputdict,globaldict=globaldict),
                outputdict, localdict, ignoreexception, exceptionhandler,outputcopy=False,globaldict=globaldict)
        decorated_function.__name__=self.name
        if taskfunction:
            decorated_function.__name__=self.name+taskfunction.__name__
        return decorated_function
    def run(self,localdict=None,outputdict=None, parallel=None, ignoreexception=None,exceptionhandler=None,globaldict=None, **kwargs):
        if outputdict==None:
            outputdict={}
        if localdict==None:
            localdict=outputdict
        if 'data' not in localdict:
            localdict['data']={}
        localdict['data'].update(self.data)
        localdict['data'].update(kwargs)
        if globaldict==None:
            globaldict=localdict
        temp_output = self.__call__(None,localdict=localdict,outputdict=outputdict, parallel=parallel,globaldict=globaldict,
                              ignoreexception=ignoreexception,exceptionhandler=exceptionhandler, **kwargs)()
        return outputdict



