"""Frozen semantic attribution rules from the 2026-10-23 experiment.

Function names are stripped of argument lists before subtree matching; a type
mentioned in a signature is not evidence that its methods executed.
"""
import re

def contains(frames, needles):
    return any(needle in name for name in frames for needle in needles)


def classify(sample):
    frames = sample['frames']
    names = [frame['name'] for frame in frames]
    native = [re.sub(r' \[clone .*?\]', '', frame['native']).replace('(anonymous namespace)::', '').split('(', 1)[0] for frame in frames if frame['native']]
    function_names = [re.sub(r' \[clone .*?\]', '', name).replace('(anonymous namespace)::', '').split('(', 1)[0] for name in names]
    allnames = function_names+native
    invalid = contains(allnames, ('JavaTypeCache::invalidate',
                                  'JavaTypeAnalysisResult::invalidateImpl'))
    lifecycle = contains(allnames, ('~JavaTypeCache', '~JavaTypeAnalysisResult',
        'AnalysisResultModel<llvm::Function, llvm::jeandle::JavaTypeAnalysis'))
    query = contains(allnames, ('getJavaType', 'getCachedJavaType',
                              'getBaseJavaType', 'phiValueType', 'factsAt'))
    lvi = contains(allnames, ('LazyValueInfo', 'getPredicateOnEdge', 'getValueOnEdge',
                              'solveBlockValue', 'isNullEdge'))
    callback = contains(allnames, ('VMCallbacksLog', 'VMCallbacksRecorder',
                                   'vmCallbacksLog', 'Replay', 'replay', 'CallbackLog'))
    dt = contains(allnames, ('DominatorTree', 'DomTreeBuilder', 'SemiNCAInfo'))
    parser = contains(allnames, ('parseIR', 'parseAssembly', 'LLParser::',
                                 'LLLexer::', 'parseBitcode'))
    base = contains(allnames, ('getBaseJavaType','valueDimension','phiValueType'))
    facts = contains(allnames, ('factsAt','edgeGuard','traceToCheckInstanceof'))
    leaf = names[0] if names else '[missing]'
    alloc = contains([leaf], ('malloc','free','realloc','calloc', 'operator new',
                             'operator delete','allocate_buffer', 'deallocate'))
    container = contains([leaf], ('DenseMap','DenseSet','SmallPtrSet','SmallVector',
                                  'try_emplace','LookupBucket','FindAndConstruct',
                                  'getHashValue','grow','insertIntoBucket'))
    typeops = contains(allnames, ('typeUnion','typeIntersect','mergePathFacts',
                                  'unionExcludedKlasses', 'isExcludedBy'))
    unknown = '[unknown]' in leaf or leaf == '[missing]'
    value_transfer = contains(allnames, ('JavaType::JavaType', 'JavaType::~JavaType', 'JavaType::operator='))
    heap = contains(allnames, ('malloc', 'calloc', 'realloc', 'cfree', 'operator new', 'operator delete', 'allocate_buffer', 'deallocate_buffer'))
    # Primary partition uses the most specific resolved semantic subtree.
    if invalid:
        group = 'javatype/invalidation'
    elif lifecycle:
        group = 'javatype/lifecycle'
    elif query:
        if lvi:
            group = 'javatype/query_lvi'
        elif callback:
            group = 'javatype/query_callback'
        elif alloc:
            group = 'javatype/query_allocation'
        elif container:
            group = 'javatype/query_container'
        elif base:
            group = 'javatype/query_base'
        elif facts:
            group = 'javatype/query_facts_other'
        elif typeops:
            group = 'javatype/query_type_operations'
        else:
            group = 'javatype/query_other'
    elif parser:
        group = 'external/parse'
    elif callback:
        group = 'external/callback'
    elif lvi:
        group = 'external/lvi'
    elif dt:
        group = 'external/dt'
    elif alloc:
        group = 'external/allocation'
    elif unknown:
        group = 'external/unknown'
    else:
        group = 'external/other'
    jt = invalid or lifecycle or query
    if contains(allnames, ('TypeCheckElimination::', 'tryEliminateTypeCheck')):
        consumer = 'TCE'
    elif contains(allnames, ('ConstantFieldFolding::','foldFieldLoad',
            'foldLoadKlassCall','foldLoadMirrorKlassCall','foldGetClassCall',
            'foldLayoutHelperCall','foldKlassInitializedCall')):
        consumer = 'CFF'
    elif contains(allnames, ('CHADevirtualization::','optimizeCallSite',
                             'optimizeMhIntrinsic','tryNarrowJavaObjType')):
        consumer = 'CHA'
    elif contains(allnames, ('RecoverTypeInfo',)):
        consumer = 'RecoverTypeInfo'
    elif lifecycle:
        consumer = 'FAM lifecycle'
    else:
        consumer = 'unresolved consumer'
    return dict(group=group,jt=jt,query=query,invalid=invalid,lifecycle=lifecycle,
                lvi=lvi,callback=callback,dt=dt,unknown=unknown,consumer=consumer,
                value_transfer=value_transfer,heap=heap,
                root_complete=contains(names, ('_start', '__libc_start_main')),
                query_boundary=contains(names,('getJavaType','getCachedJavaType')))
