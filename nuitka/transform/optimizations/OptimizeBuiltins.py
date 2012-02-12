#     Copyright 2012, Kay Hayen, mailto:kayhayen@gmx.de
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     If you submit patches or make the software available to licensors of
#     this software in either form, you automatically them grant them a
#     license for your part of the code under "Apache License 2.0" unless you
#     choose to remove this notice.
#
#     Kay Hayen uses the right to license his code under only GPL version 3,
#     to discourage a fork of Nuitka before it is "finished". He will later
#     make a new "Nuitka" release fully under "Apache License 2.0".
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, version 3 of the License.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#     Please leave the whole of this copyright notice intact.
#
""" Replace builtins with alternative implementations more optimized or capable of the task.

"""

from .OptimizeBase import (
    OptimizationDispatchingVisitorBase,
    OptimizationVisitorBase,
    makeRaiseExceptionReplacementExpressionFromInstance,
    makeBuiltinExceptionRefReplacementNode,
    makeBuiltinRefReplacementNode,
    makeConstantReplacementNode
)

from nuitka.Utils import getPythonVersion

from nuitka.nodes.BuiltinRangeNode import CPythonExpressionBuiltinRange
from nuitka.nodes.BuiltinDictNode import CPythonExpressionBuiltinDict
from nuitka.nodes.BuiltinOpenNode import CPythonExpressionBuiltinOpen
from nuitka.nodes.BuiltinVarsNode import CPythonExpressionBuiltinVars
from nuitka.nodes.BuiltinIteratorNodes import (
    CPythonExpressionBuiltinNext1,
    CPythonExpressionBuiltinNext2,
    CPythonExpressionBuiltinIter1,
    CPythonExpressionBuiltinIter2,
    CPythonExpressionBuiltinLen
)
from nuitka.nodes.BuiltinTypeNodes import (
    CPythonExpressionBuiltinFloat,
    CPythonExpressionBuiltinTuple,
    CPythonExpressionBuiltinList,
    CPythonExpressionBuiltinBool,
    CPythonExpressionBuiltinInt,
    CPythonExpressionBuiltinStr
)
if getPythonVersion() < 300:
    from nuitka.nodes.BuiltinTypeNodes import CPythonExpressionBuiltinLong
from nuitka.nodes.BuiltinFormatNodes import (
    CPythonExpressionBuiltinBin,
    CPythonExpressionBuiltinOct,
    CPythonExpressionBuiltinHex,
)
from nuitka.nodes.BuiltinDecodingNodes import (
    CPythonExpressionBuiltinChr,
    CPythonExpressionBuiltinOrd
)
from nuitka.nodes.ExceptionNodes import CPythonExpressionBuiltinMakeException
from nuitka.nodes.TypeNode import CPythonExpressionBuiltinType1
from nuitka.nodes.CallNode import CPythonExpressionFunctionCall
from nuitka.nodes.AttributeNode import CPythonExpressionAttributeLookup
from nuitka.nodes.ImportNodes import CPythonExpressionBuiltinImport, CPythonExpressionImportModule
from nuitka.nodes.OperatorNodes import CPythonExpressionOperationUnary
from nuitka.nodes.ClassNodes import CPythonExpressionBuiltinType3

from nuitka.nodes.ExecEvalNodes import (
    CPythonExpressionBuiltinEval,
    CPythonExpressionBuiltinExec,
    CPythonExpressionBuiltinExecfile,
    CPythonStatementExec
)
from nuitka.nodes.GlobalsLocalsNodes import (
    CPythonExpressionBuiltinGlobals,
    CPythonExpressionBuiltinLocals,
    CPythonExpressionBuiltinDir0
)

from nuitka.Builtins import builtin_exception_names, builtin_names

from . import BuiltinOptimization



# TODO: The maybe local variable should have a read only indication too, but right
# now it's not yet done.

def _isReadOnlyModuleVariable( variable ):
    return ( variable.isModuleVariable() and variable.getReadOnlyIndicator() is True ) or \
           variable.isMaybeLocalVariable()

class ReplaceBuiltinsVisitorBase( OptimizationDispatchingVisitorBase ):
    """ Replace calls to builtin names by builtin nodes if possible or necessary.

    """

    # Many methods of this class could be functions, but we want it scoped on the class
    # level anyway. pylint: disable=R0201

    def __init__( self, dispatch_dict ):
        OptimizationDispatchingVisitorBase.__init__(
            self,
            dispatch_dict = dispatch_dict
        )

    def getKey( self, node ):
        if node.isExpressionFunctionCall():
            called = node.getCalled()

            if called.isExpressionVariableRef():
                variable = called.getVariable()

                assert variable is not None, node

                if _isReadOnlyModuleVariable( variable ):
                    return variable.getName()

    def onEnterNode( self, node ):
        new_node = OptimizationDispatchingVisitorBase.onEnterNode( self, node )

        if new_node is not None:

            # The exec statement must be treated differently.
            if new_node.isStatementExec():
                assert node.parent.isStatementExpressionOnly(), node.getSourceReference()

                node.parent.replaceWith( new_node = new_node )
            else:
                node.replaceWith( new_node = new_node )

            if new_node.isExpressionBuiltinImport():
                self.signalChange(
                    "new_builtin new_import",
                    node.getSourceReference(),
                    message = "Replaced dynamic builtin import %s with static module import." % new_node.kind
                )
            elif new_node.isExpressionBuiltin() or new_node.isStatementExec():
                self.signalChange(
                    "new_builtin",
                    node.getSourceReference(),
                    message = "Replaced call to builtin %s with builtin call." % new_node.kind
                )
            elif new_node.isExpressionFunctionCall():
                self.signalChange(
                    "new_raise new_variable",
                    node.getSourceReference(),
                    message = "Replaced call to builtin %s with exception raising call." % new_node.kind
                )
            elif new_node.isExpressionOperationUnary():
                self.signalChange(
                    "new_expression",
                    node.getSourceReference(),
                    message = "Replaced call to builtin %s with exception raising call." % new_node.kind
                )
            else:
                assert False

            assert node.isExpressionFunctionCall

            called = node.getCalled()
            assert called.isExpressionVariableRef()

            variable = called.getVariable()

            owner = variable.getOwner()
            owner.reconsiderVariable( variable )

            if owner.isExpressionFunctionBody():
                self.signalChange(
                    "var_usage",
                    owner.getSourceReference(),
                    message = "Reduced variable '%s' usage of function %s." % ( variable.getName(), owner )
                )

class ReplaceBuiltinsCriticalVisitor( ReplaceBuiltinsVisitorBase ):
    # Many methods of this class could be functions, but we want it scoped on the class
    # level anyway. pylint: disable=R0201

    def __init__( self ):
        ReplaceBuiltinsVisitorBase.__init__(
            self,
            dispatch_dict = {
                "globals"    : self.globals_extractor,
                "locals"     : self.locals_extractor,
                "eval"       : self.eval_extractor,
                "exec"       : self.exec_extractor,
                "execfile"   : self.execfile_extractor,
            }
        )


    def execfile_extractor( self, node ):
        def wrapExpressionBuiltinExecfileCreation( filename, globals_arg, locals_arg, source_ref ):

            if node.getParentVariableProvider().isExpressionClassBody():
                # In a case, the copy-back must be done and will only be done correctly by
                # the code for exec statements.

                use_call = CPythonStatementExec
            else:
                use_call = CPythonExpressionBuiltinExecfile

            return use_call(
                source_code = CPythonExpressionFunctionCall(
                    called_expression = CPythonExpressionAttributeLookup(
                        expression     = CPythonExpressionBuiltinOpen(
                            filename   = filename,
                            mode       = makeConstantReplacementNode(
                                constant = "rU",
                                node     = node
                            ),
                            buffering  = None,
                            source_ref = source_ref
                        ),
                        attribute_name = "read",
                        source_ref     = source_ref
                    ),
                    positional_args  = (),
                    pairs            = (),
                    list_star_arg    = None,
                    dict_star_arg    = None,
                    source_ref       = source_ref
                ),
                globals_arg = globals_arg,
                locals_arg  = locals_arg,
                source_ref = source_ref
            )

        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = wrapExpressionBuiltinExecfileCreation,
            builtin_spec  = BuiltinOptimization.builtin_execfile_spec
        )

    def eval_extractor( self, node ):
        # TODO: Should precompute error as well: TypeError: eval() takes no keyword arguments

        positional_args = node.getPositionalArguments()

        return CPythonExpressionBuiltinEval(
            source_code  = positional_args[0],
            globals_arg  = positional_args[1] if len( positional_args ) > 1 else None,
            locals_arg   = positional_args[2] if len( positional_args ) > 2 else None,
            source_ref   = node.getSourceReference()
        )

    def exec_extractor( self, node ):
        # TODO: Should precompute error as well: TypeError: exec() takes no keyword arguments

        positional_args = node.getPositionalArguments()

        return CPythonExpressionBuiltinExec(
            source_code  = positional_args[0],
            globals_arg  = positional_args[1] if len( positional_args ) > 1 else None,
            locals_arg   = positional_args[2] if len( positional_args ) > 2 else None,
            source_ref   = node.getSourceReference()
        )

    @staticmethod
    def _pickLocalsForNode( node ):
        """ Pick a locals default for the given node. """

        provider = node.getParentVariableProvider()

        if provider.isModule():
            return CPythonExpressionBuiltinGlobals(
                source_ref = node.getSourceReference()
            )
        else:
            return CPythonExpressionBuiltinLocals(
                source_ref = node.getSourceReference()
            )

    @staticmethod
    def _pickGlobalsForNode( node ):
        """ Pick a globals default for the given node. """

        return CPythonExpressionBuiltinGlobals(
            source_ref = node.getSourceReference()
        )

    def globals_extractor( self, node ):
        assert node.isEmptyCall()

        return self._pickGlobalsForNode( node )

    def locals_extractor( self, node ):
        assert node.isEmptyCall()

        return self._pickLocalsForNode( node )


class ReplaceBuiltinsOptionalVisitor( ReplaceBuiltinsVisitorBase ):
    # Many methods of this class could be functions, but we want it scoped on the class
    # level anyway. pylint: disable=R0201

    def __init__( self ):
        dispatch_dict = {
            "dir"        : self.dir_extractor,
            "vars"       : self.vars_extractor,
            "__import__" : self.import_extractor,
            "chr"        : self.chr_extractor,
            "ord"        : self.ord_extractor,
            "bin"        : self.bin_extractor,
            "oct"        : self.oct_extractor,
            "hex"        : self.hex_extractor,
            "type"       : self.type_extractor,
            "iter"       : self.iter_extractor,
            "next"       : self.next_extractor,
            "range"      : self.range_extractor,
            "tuple"      : self.tuple_extractor,
            "list"       : self.list_extractor,
            "dict"       : self.dict_extractor,
            "float"      : self.float_extractor,
            "str"        : self.str_extractor,
            "bool"       : self.bool_extractor,
            "int"        : self.int_extractor,
            "repr"       : self.repr_extractor,
            "len"        : self.len_extractor,
        }

        if getPythonVersion() < 300:
            dispatch_dict[ "long" ] = self.long_extractor

        for builtin_exception_name in builtin_exception_names:
            dispatch_dict[ builtin_exception_name ] = self.exceptions_extractor

        ReplaceBuiltinsVisitorBase.__init__(
            self,
            dispatch_dict = dispatch_dict
        )

    def dir_extractor( self, node ):
        # Only treat the empty dir() call, leave the others alone for now.
        if not node.isEmptyCall():
            return None

        return CPythonExpressionBuiltinDir0(
            source_ref = node.getSourceReference()
        )

    def vars_extractor( self, node ):
        positional_args = node.getPositionalArguments()

        if len( positional_args ) == 0:
            if node.getParentVariableProvider().isModule():
                return CPythonExpressionBuiltinGlobals(
                    source_ref = node.getSourceReference()
                )
            else:
                return CPythonExpressionBuiltinLocals(
                    source_ref = node.getSourceReference()
                )
        elif len( positional_args ) == 1:
            return CPythonExpressionBuiltinVars(
                source     = positional_args[ 0 ],
                source_ref = node.getSourceReference()
            )
        else:
            assert False

    def import_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinImport,
            builtin_spec  = BuiltinOptimization.builtin_import_spec
        )

    def type_extractor( self, node ):
        positional_args = node.getPositionalArguments()

        if len( positional_args ) == 1:
            return CPythonExpressionBuiltinType1(
                value      = positional_args[0],
                source_ref = node.getSourceReference()
            )
        elif len( positional_args ) == 3:
            return CPythonExpressionBuiltinType3(
                type_name  = positional_args[0],
                bases      = positional_args[1],
                type_dict  = positional_args[2],
                source_ref = node.getSourceReference()
            )

    def iter_extractor( self, node ):
        positional_args = node.getPositionalArguments()

        if len( positional_args ) == 1:
            return CPythonExpressionBuiltinIter1(
                value      = positional_args[0],
                source_ref = node.getSourceReference()
            )
        elif len( positional_args ) == 2:
            return CPythonExpressionBuiltinIter2(
                call_able  = positional_args[0],
                sentinel   = positional_args[1],
                source_ref = node.getSourceReference()
            )

    def next_extractor( self, node ):
        positional_args = node.getPositionalArguments()

        if len( positional_args ) == 1:
            return CPythonExpressionBuiltinNext1(
                value      = positional_args[0],
                source_ref = node.getSourceReference()
            )
        else:
            return CPythonExpressionBuiltinNext2(
                iterator   = positional_args[0],
                default    = positional_args[1],
                source_ref = node.getSourceReference()
            )

    def dict_extractor( self, node ):
        # The dict is a bit strange in that it accepts a position parameter, or not, but
        # won't have a default.

        def wrapExpressionBuiltinDictCreation( positional_args, pairs, source_ref ):
            if len( positional_args ) > 1:
                return CPythonExpressionFunctionCall(
                    called_expression = makeRaiseExceptionReplacementExpressionFromInstance(
                        expression     = node,
                        exception      = TypeError(
                            "dict expected at most 1 arguments, got %d" % len( positional_args )
                        )
                    ),
                    positional_args   = positional_args,
                    list_star_arg     = None,
                    dict_star_arg     = None,
                    pairs             = pairs,
                    source_ref        = source_ref
                )

            return CPythonExpressionBuiltinDict(
                pos_arg    = positional_args[0] if positional_args else None,
                pairs      = pairs,
                source_ref = node.getSourceReference()
            )

        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = wrapExpressionBuiltinDictCreation,
            builtin_spec  = BuiltinOptimization.builtin_dict_spec
        )

    def chr_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinChr,
            builtin_spec  = BuiltinOptimization.builtin_chr_spec
        )

    def ord_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinOrd,
            builtin_spec  = BuiltinOptimization.builtin_ord_spec
        )

    def bin_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinBin,
            builtin_spec  = BuiltinOptimization.builtin_bin_spec
        )

    def oct_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinOct,
            builtin_spec  = BuiltinOptimization.builtin_oct_spec
        )

    def hex_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinHex,
            builtin_spec  = BuiltinOptimization.builtin_hex_spec
        )

    def repr_extractor( self, node ):
        def makeReprOperator( operand, source_ref ):
            return CPythonExpressionOperationUnary(
                operator   = "Repr",
                operand    = operand,
                source_ref = source_ref
            )

        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = makeReprOperator,
            builtin_spec  = BuiltinOptimization.builtin_repr_spec
        )

    def range_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinRange,
            builtin_spec  = BuiltinOptimization.builtin_range_spec
        )

    def len_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinLen,
            builtin_spec  = BuiltinOptimization.builtin_len_spec
        )

    def tuple_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinTuple,
            builtin_spec  = BuiltinOptimization.builtin_tuple_spec
        )

    def list_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinList,
            builtin_spec  = BuiltinOptimization.builtin_list_spec
        )

    def float_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinFloat,
            builtin_spec  = BuiltinOptimization.builtin_float_spec
        )

    def str_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinStr,
            builtin_spec  = BuiltinOptimization.builtin_str_spec
        )

    def bool_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinBool,
            builtin_spec  = BuiltinOptimization.builtin_bool_spec
        )

    def int_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinInt,
            builtin_spec  = BuiltinOptimization.builtin_int_spec
        )

    def long_extractor( self, node ):
        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = CPythonExpressionBuiltinLong,
            builtin_spec  = BuiltinOptimization.builtin_long_spec
        )

    def exceptions_extractor( self, node ):
        exception_name = node.getCalled().getVariable().getName()

        def createBuiltinMakeException( args, source_ref ):
            return CPythonExpressionBuiltinMakeException(
                exception_name = exception_name,
                args           = args,
                source_ref     = source_ref
            )

        return BuiltinOptimization.extractBuiltinArgs(
            node          = node,
            builtin_class = createBuiltinMakeException,
            builtin_spec  = BuiltinOptimization.BuiltinParameterSpecExceptions(
                name          = exception_name,
                default_count = 0
            )
        )

_quick_names = {
    "None"  : None,
    "True"  : True,
    "False" : False
}

class ReplaceBuiltinsExceptionsVisitor( OptimizationVisitorBase ):
    def onEnterNode( self, node ):
        if node.isExpressionVariableRef():
            variable = node.getVariable()

            if variable is not None:
                variable_name = variable.getName()

                if variable_name in builtin_exception_names and _isReadOnlyModuleVariable( variable ):
                    new_node = makeBuiltinExceptionRefReplacementNode(
                        exception_name = variable.getName(),
                        node           = node
                    )

                    node.replaceWith( new_node )

                    self.signalChange(
                        "new_raise new_variable",
                        node.getSourceReference(),
                        message = "Replaced access to read only module variable with exception %s." % (
                           variable.getName()
                        )
                    )

                    assert node.parent is new_node.parent
                elif variable_name in _quick_names and _isReadOnlyModuleVariable( variable ):
                    new_node = makeConstantReplacementNode(
                        node     = node,
                        constant = _quick_names[ variable_name ]
                    )

                    node.replaceWith( new_node )

                    self.signalChange(
                        "new_constant",
                        node.getSourceReference(),
                        "Builtin constant was predicted to constant."
                    )



class PrecomputeBuiltinsVisitor( OptimizationDispatchingVisitorBase ):
    """ Precompute builtins with constant arguments if possible. """
    # Many methods of this class could be functions, but we want it scoped on the class
    # level anyway. pylint: disable=R0201

    def __init__( self ):
        dispatch_dict = {
            "chr"        : self.chr_extractor,
            "ord"        : self.ord_extractor,
            "bin"        : self.bin_extractor,
            "oct"        : self.oct_extractor,
            "hex"        : self.hex_extractor,
            "type1"      : self.type1_extractor,
            "range"      : self.range_extractor,
            "len"        : self.len_extractor,
            "tuple"      : self.tuple_extractor,
            "list"       : self.list_extractor,
            "dict"       : self.dict_extractor,
            "float"      : self.float_extractor,
            "str"        : self.str_extractor,
            "bool"       : self.bool_extractor,
            "int"        : self.int_extractor,
            "long"       : self.long_extractor,
            "import"     : self.import_extractor
        }

        if getPythonVersion() < 300:
            dispatch_dict[ "long" ] = self.long_extractor

        OptimizationDispatchingVisitorBase.__init__(
            self,
            dispatch_dict = dispatch_dict
        )

    def getKey( self, node ):
        if node.isExpressionBuiltin():
            return node.kind.replace( "EXPRESSION_BUILTIN_", "" ).lower()

    def type1_extractor( self, node ):
        value = node.getValue()

        if value.isExpressionConstantRef():
            value = value.getConstant()

            if value is not None:
                type_name = value.__class__.__name__

                assert (type_name in builtin_names), (type_name, builtin_names)

                new_node = makeBuiltinRefReplacementNode(
                    builtin_name = type_name,
                    node         = node
                )

                self.signalChange(
                    "new_builtin",
                    node.getSourceReference(),
                    message = "Replaced predictable type lookup of constant with builtin type '%s'." % type_name
                )

                node.replaceWith( new_node )



    def range_extractor( self, node ):
        new_node, tags, descr = node.computeNode()

        if new_node is not node:
            node.replaceWith( new_node )

            self.signalChange(
                tags,
                node.getSourceReference(),
                descr
            )

    def _extractConstantBuiltinCall( self, node, builtin_spec, given_values ):
        def isValueListConstant( values ):
            for sub_value in values:
                if sub_value.isExpressionKeyValuePair():
                    if not sub_value.getKey().isExpressionConstantRef():
                        return False
                    if not sub_value.getValue().isExpressionConstantRef():
                        return False
                elif not sub_value.isExpressionConstantRef():
                    return False

            return True

        for value in given_values:
            if value:
                if type( value ) in ( list, tuple ):
                    if not isValueListConstant( value ):
                        break
                elif not value.isExpressionConstantRef():
                    break
        else:
            self.replaceWithComputationResult(
                node        = node,
                computation = lambda : builtin_spec.simulateCall( given_values ),
                description = "Builtin call %s" % builtin_spec.getName()
            )

    def dict_extractor( self, node ):
        pos_arg = node.getPositionalArgument()

        if pos_arg is not None:
            pos_args = ( pos_arg, )
        else:
            pos_args = None

        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_dict_spec,
            given_values = ( pos_args, node.getNamedArgumentPairs() )
        )

    def chr_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_chr_spec,
            given_values = ( node.getValue(), )
        )

    def ord_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_ord_spec,
            given_values = ( node.getValue(), )
        )

    def bin_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_bin_spec,
            given_values = ( node.getValue(), )
        )

    def oct_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_oct_spec,
            given_values = ( node.getValue(), )
        )

    def hex_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_hex_spec,
            given_values = ( node.getValue(), )
        )

    def len_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_len_spec,
            given_values = ( node.getValue(), )
        )

    def tuple_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_tuple_spec,
            given_values = ( node.getValue(), )
        )

    def list_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_list_spec,
            given_values = ( node.getValue(), )
        )

    def float_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_float_spec,
            given_values = ( node.getValue(), )
        )

    def str_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_str_spec,
            given_values = ( node.getValue(), )
        )


    def bool_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_bool_spec,
            given_values = ( node.getValue(), )
        )

    def int_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_int_spec,
            given_values = ( node.getValue(), node.getBase() )
        )


    def long_extractor( self, node ):
        return self._extractConstantBuiltinCall(
            node         = node,
            builtin_spec = BuiltinOptimization.builtin_long_spec,
            given_values = ( node.getValue(), node.getBase() )
        )

    def import_extractor( self, node ):
        module_name = node.getImportName()
        fromlist = node.getFromList()
        level = node.getLevel()

        # TODO: In fact, if the module is not a package, we don't have to insist on the
        # fromlist that much, but normally it's not used for anything but packages, so
        # it will be rare.

        if module_name.isExpressionConstantRef() and fromlist.isExpressionConstantRef() \
             and level.isExpressionConstantRef():
            new_node = CPythonExpressionImportModule(
                module_name = module_name.getConstant(),
                import_list = fromlist.getConstant(),
                level       = level.getConstant(),
                source_ref  = node.getSourceReference()
            )

            node.replaceWith( new_node )

            self.signalChange(
                "new_import",
                node.getSourceReference(),
                message = "Replaced call to builtin %s with builtin call." % node.kind
            )
