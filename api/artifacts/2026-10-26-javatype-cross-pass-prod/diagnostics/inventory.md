# 语料清单与不利样本

## 语料规模与覆盖率

- 录制 root method 总数: 76
- 入选(合格)样本数: 64
- 拒绝样本数: 12
- 入选样本覆盖的程序数: 6

| 程序 | 入选样本数 | 方法 |
|---|---|---|
| ArrayShapes | 6 | ArrayShapes_arrayLengthLoop, ArrayShapes_checkedArrayElement, ArrayShapes_sumArrayElements, ArrayShapes_sumNestedArrays, ArrayShapes_sumPrimitiveArray, ArrayShapes_traverseList |
| CollectionShapes | 14 | CollectionShapes$Node_<init>, CollectionShapes_visitBimorphic, java_lang_Object_<init>, java_lang_StringLatin1_charAt, java_lang_String_checkIndex, java_lang_String_coder, java_lang_String_hashCode, java_lang_String_isLatin1, java_lang_String_length, java_util_ArrayList$Itr_checkForComodification, java_util_ArrayList$Itr_hasNext, java_util_ArrayList$Itr_next, java_util_HashMap_hash, jdk_internal_util_Preconditions_checkIndex |
| ConstantShapes | 6 | ConstantShapes_foldWithTypeCheck, ConstantShapes_readInstanceFinals, ConstantShapes_readMutableField, java_lang_String_coder, java_lang_String_length, java_util_Objects_requireNonNull |
| InlineShapes | 6 | InlineShapes_addBoth, InlineShapes_addOther, InlineShapes_addValue, InlineShapes_inlineChain, InlineShapes_nestedInline, InlineShapes_virtualInline |
| NegativeShapes | 22 | NegativeShapes_arithmeticOnly, NegativeShapes_mathOnly, NegativeShapes_numericArray, java_lang_AbstractStringBuilder_getValue, java_lang_AbstractStringBuilder_length, java_lang_Enum_ordinal, java_lang_StringLatin1_charAt, java_lang_String_checkIndex, java_lang_String_coder, java_lang_String_isLatin1, java_lang_String_length, java_lang_invoke_LambdaForm$BasicType_basicTypeClass, java_lang_invoke_LambdaForm$Name_index, java_lang_invoke_MemberName_getDeclaringClass, java_lang_invoke_MethodTypeForm_parameterSlotCount, java_lang_invoke_MethodType_form, java_lang_invoke_MethodType_ptypes, java_lang_invoke_MethodType_returnType, jdk_internal_util_Preconditions_checkIndex, jdk_internal_util_StrongReferenceKey_get, jdk_internal_util_WeakReferenceKey_hashCode, sun_invoke_util_Wrapper_basicTypeChar |
| TypeShapes | 10 | TypeShapes$Base_<init>, TypeShapes$Circle_area, TypeShapes$Square_area, TypeShapes_guardedFieldLoad, TypeShapes_instanceofChain, TypeShapes_monomorphicCall, TypeShapes_polymorphicCall, TypeShapes_repeatedFieldLoads, TypeShapes_twoFieldLoads, java_lang_Object_<init> |

### 拒绝样本及原因

| 程序 | 方法 | 拒绝原因 |
|---|---|---|
| CollectionShapes | CollectionShapes_allocateInLoop | replay failed in mode original (exit -6) |
| CollectionShapes | CollectionShapes_iterateList | replay failed in mode original (exit -6) |
| CollectionShapes | CollectionShapes_readMap | replay failed in mode original (exit -6) |
| CollectionShapes | CollectionShapes_stringWork | replay failed in mode original (exit -6) |
| CollectionShapes | java_lang_String_charAt | replay failed in mode original (exit -6) |
| CollectionShapes | java_util_HashMap_getNode | replay failed in mode original (exit -6) |
| CollectionShapes | java_util_HashMap_get | replay failed in mode original (exit -6) |
| ConstantShapes | ConstantShapes_readHolderFields | replay failed in mode original (exit -6) |
| ConstantShapes | ConstantShapes_readStaticFinals | replay failed in mode original (exit -6) |
| NegativeShapes | NegativeShapes_stringLength | replay failed in mode original (exit -6) |
| NegativeShapes | java_lang_String_charAt | replay failed in mode original (exit -6) |
| TypeShapes | TypeShapes$Mid_<init> | replay failed in mode original (exit -6) |

拒绝原因统计: replay failed in mode original (exit -6) x12

## 零查询样本（不触发 Java 类型子系统的样本）

入选样本共 64 个，其中三模式查询数均为 0 的样本 0 个：

无

## 负收益样本清单（按净收益升序）

### original->cross_pass

- 负收益样本数: 37 / 64 (57.8%)
- 最差样本净收益: -2.362%

| 样本 | 净收益(%) | 扣 no-op 后净收益(%) | 基线 CPU(s) | 候选 CPU(s) | 候选模式查询数 |
|---|---|---|---|---|---|
| ArrayShapes	ArrayShapes_traverseList | -2.362 | -2.828 | 0.0230 | 0.0236 | 2 |
| NegativeShapes	java_lang_invoke_MethodType_returnType | -1.695 | -2.049 | 0.0222 | 0.0225 | 2 |
| InlineShapes	InlineShapes_addBoth | -1.649 | -2.023 | 0.0227 | 0.0231 | 2 |
| TypeShapes	TypeShapes_instanceofChain | -1.382 | -1.647 | 0.0238 | 0.0241 | 6 |
| TypeShapes	java_lang_Object_<init> | -1.382 | -1.695 | 0.0221 | 0.0224 | 2 |
| ConstantShapes	java_lang_String_coder | -1.341 | -1.618 | 0.0221 | 0.0224 | 2 |
| NegativeShapes	jdk_internal_util_WeakReferenceKey_hashCode | -1.321 | -1.608 | 0.0220 | 0.0223 | 2 |
| CollectionShapes	java_lang_String_isLatin1 | -1.223 | -1.458 | 0.0224 | 0.0227 | 2 |
| NegativeShapes	jdk_internal_util_Preconditions_checkIndex | -1.223 | -1.482 | 0.0222 | 0.0225 | 2 |
| NegativeShapes	java_lang_AbstractStringBuilder_getValue | -1.178 | -1.401 | 0.0222 | 0.0225 | 2 |
| TypeShapes	TypeShapes_twoFieldLoads | -1.149 | -1.395 | 0.0223 | 0.0225 | 2 |
| NegativeShapes	NegativeShapes_numericArray | -1.148 | -1.379 | 0.0242 | 0.0245 | 2 |
| ConstantShapes	ConstantShapes_foldWithTypeCheck | -1.124 | -1.322 | 0.0241 | 0.0244 | 7 |
| TypeShapes	TypeShapes$Square_area | -1.091 | -1.307 | 0.0221 | 0.0224 | 2 |
| InlineShapes	InlineShapes_addValue | -1.048 | -1.276 | 0.0221 | 0.0223 | 2 |
| CollectionShapes	java_util_ArrayList$Itr_checkForComodification | -0.970 | -1.158 | 0.0224 | 0.0226 | 2 |
| TypeShapes	TypeShapes_monomorphicCall | -0.969 | -1.153 | 0.0227 | 0.0229 | 4 |
| CollectionShapes	java_lang_String_hashCode | -0.941 | -1.121 | 0.0224 | 0.0226 | 2 |
| NegativeShapes	jdk_internal_util_StrongReferenceKey_get | -0.937 | -1.110 | 0.0224 | 0.0226 | 2 |
| NegativeShapes	NegativeShapes_arithmeticOnly | -0.895 | -1.050 | 0.0238 | 0.0240 | 2 |
| CollectionShapes	jdk_internal_util_Preconditions_checkIndex | -0.894 | -1.107 | 0.0222 | 0.0224 | 2 |
| CollectionShapes	java_lang_String_checkIndex | -0.862 | -1.036 | 0.0224 | 0.0225 | 3 |
| CollectionShapes	java_lang_StringLatin1_charAt | -0.785 | -0.959 | 0.0228 | 0.0230 | 3 |
| CollectionShapes	java_lang_String_length | -0.780 | -0.937 | 0.0230 | 0.0232 | 2 |
| NegativeShapes	java_lang_Enum_ordinal | -0.736 | -0.879 | 0.0223 | 0.0225 | 2 |
| NegativeShapes	java_lang_StringLatin1_charAt | -0.652 | -0.797 | 0.0228 | 0.0230 | 3 |
| CollectionShapes	java_util_ArrayList$Itr_hasNext | -0.637 | -0.781 | 0.0225 | 0.0226 | 2 |
| ArrayShapes	ArrayShapes_sumPrimitiveArray | -0.611 | -0.729 | 0.0243 | 0.0245 | 2 |
| CollectionShapes	java_lang_String_coder | -0.541 | -0.668 | 0.0223 | 0.0224 | 2 |
| ArrayShapes	ArrayShapes_checkedArrayElement | -0.511 | -0.610 | 0.0236 | 0.0237 | 6 |
| InlineShapes	InlineShapes_virtualInline | -0.473 | -0.560 | 0.0228 | 0.0229 | 3 |
| NegativeShapes	java_lang_String_length | -0.451 | -0.547 | 0.0229 | 0.0230 | 2 |
| NegativeShapes	java_lang_String_isLatin1 | -0.152 | -0.182 | 0.0223 | 0.0223 | 2 |
| CollectionShapes	java_lang_Object_<init> | -0.090 | -0.107 | 0.0222 | 0.0222 | 2 |
| InlineShapes	InlineShapes_inlineChain | -0.020 | -0.023 | 0.0245 | 0.0245 | 3 |
| NegativeShapes	sun_invoke_util_Wrapper_basicTypeChar | -0.009 | -0.011 | 0.0222 | 0.0222 | 2 |
| NegativeShapes	java_lang_invoke_MethodType_ptypes | -0.008 | -0.009 | 0.0223 | 0.0223 | 2 |

### pass_local->cross_pass

- 负收益样本数: 36 / 64 (56.2%)
- 最差样本净收益: -3.445%

| 样本 | 净收益(%) | 扣 no-op 后净收益(%) | 基线 CPU(s) | 候选 CPU(s) | 候选模式查询数 |
|---|---|---|---|---|---|
| ArrayShapes	ArrayShapes_traverseList | -3.445 | -4.134 | 0.0228 | 0.0236 | 2 |
| ConstantShapes	ConstantShapes_foldWithTypeCheck | -3.303 | -3.900 | 0.0236 | 0.0244 | 7 |
| ArrayShapes	ArrayShapes_arrayLengthLoop | -2.192 | -2.595 | 0.0244 | 0.0250 | 4 |
| TypeShapes	TypeShapes_instanceofChain | -2.107 | -2.514 | 0.0236 | 0.0241 | 6 |
| NegativeShapes	java_lang_Enum_ordinal | -1.944 | -2.326 | 0.0221 | 0.0225 | 2 |
| InlineShapes	InlineShapes_addBoth | -1.740 | -2.135 | 0.0227 | 0.0231 | 2 |
| CollectionShapes	java_lang_String_coder | -1.713 | -2.118 | 0.0220 | 0.0224 | 2 |
| CollectionShapes	java_lang_String_isLatin1 | -1.707 | -2.037 | 0.0223 | 0.0227 | 2 |
| CollectionShapes	java_util_ArrayList$Itr_hasNext | -1.532 | -1.881 | 0.0223 | 0.0226 | 2 |
| NegativeShapes	NegativeShapes_mathOnly | -1.525 | -1.921 | 0.0224 | 0.0228 | 2 |
| CollectionShapes	java_lang_String_length | -1.468 | -1.766 | 0.0228 | 0.0232 | 2 |
| ArrayShapes	ArrayShapes_sumPrimitiveArray | -1.359 | -1.623 | 0.0242 | 0.0245 | 2 |
| NegativeShapes	jdk_internal_util_Preconditions_checkIndex | -1.116 | -1.352 | 0.0223 | 0.0225 | 2 |
| ArrayShapes	ArrayShapes_sumArrayElements | -1.108 | -1.312 | 0.0245 | 0.0248 | 3 |
| NegativeShapes	java_lang_invoke_MethodType_returnType | -1.080 | -1.304 | 0.0223 | 0.0225 | 2 |
| ConstantShapes	java_util_Objects_requireNonNull | -1.019 | -1.230 | 0.0220 | 0.0222 | 2 |
| CollectionShapes	java_util_ArrayList$Itr_checkForComodification | -1.001 | -1.195 | 0.0224 | 0.0226 | 2 |
| CollectionShapes	CollectionShapes_visitBimorphic | -0.989 | -1.185 | 0.0226 | 0.0228 | 5 |
| CollectionShapes	java_lang_String_hashCode | -0.972 | -1.158 | 0.0224 | 0.0226 | 2 |
| TypeShapes	java_lang_Object_<init> | -0.867 | -1.062 | 0.0222 | 0.0224 | 2 |
| NegativeShapes	java_lang_String_length | -0.782 | -0.948 | 0.0228 | 0.0230 | 2 |
| NegativeShapes	sun_invoke_util_Wrapper_basicTypeChar | -0.778 | -0.941 | 0.0221 | 0.0222 | 2 |
| CollectionShapes	java_lang_String_checkIndex | -0.773 | -0.929 | 0.0224 | 0.0225 | 3 |
| ConstantShapes	ConstantShapes_readMutableField | -0.740 | -0.887 | 0.0220 | 0.0222 | 2 |
| InlineShapes	InlineShapes_addValue | -0.670 | -0.815 | 0.0221 | 0.0223 | 2 |
| NegativeShapes	java_lang_AbstractStringBuilder_getValue | -0.581 | -0.690 | 0.0224 | 0.0225 | 2 |
| NegativeShapes	java_lang_invoke_LambdaForm$Name_index | -0.564 | -0.673 | 0.0221 | 0.0223 | 2 |
| TypeShapes	TypeShapes_repeatedFieldLoads | -0.513 | -0.607 | 0.0226 | 0.0227 | 2 |
| NegativeShapes	NegativeShapes_numericArray | -0.499 | -0.598 | 0.0243 | 0.0245 | 2 |
| TypeShapes	TypeShapes$Circle_area | -0.404 | -0.481 | 0.0222 | 0.0223 | 2 |
| NegativeShapes	jdk_internal_util_WeakReferenceKey_hashCode | -0.367 | -0.445 | 0.0222 | 0.0223 | 2 |
| ConstantShapes	java_lang_String_coder | -0.322 | -0.388 | 0.0223 | 0.0224 | 2 |
| InlineShapes	InlineShapes_virtualInline | -0.289 | -0.342 | 0.0228 | 0.0229 | 3 |
| TypeShapes	TypeShapes_polymorphicCall | -0.213 | -0.252 | 0.0227 | 0.0228 | 5 |
| NegativeShapes	jdk_internal_util_StrongReferenceKey_get | -0.188 | -0.223 | 0.0225 | 0.0226 | 2 |
| TypeShapes	TypeShapes_twoFieldLoads | -0.186 | -0.225 | 0.0225 | 0.0225 | 2 |

