#     Copyright 2025, Kay Hayen, mailto:kay.hayen@gmail.com find license text at end of file


""" Reformulation of import statements.

Consult the Developer Manual for information. TODO: Add ability to sync
source code comments with Developer Manual sections.

"""

# spell-checker: ignore fromlist,asname

from nuitka.importing.ImportResolving import resolveModuleName
from nuitka.nodes.ConstantRefNodes import makeConstantRefNode
from nuitka.nodes.GlobalsLocalsNodes import ExpressionBuiltinGlobals
from nuitka.nodes.ImportNodes import (
    ExpressionBuiltinImport,
    ExpressionImportName,
    StatementImportStar,
    makeExpressionImportModuleFixed,
)
from nuitka.nodes.NodeMakingHelpers import mergeStatements
from nuitka.nodes.StatementNodes import StatementsSequence
from nuitka.nodes.VariableAssignNodes import makeStatementAssignmentVariable
from nuitka.nodes.VariableNameNodes import StatementAssignmentVariableName
from nuitka.nodes.VariableRefNodes import ExpressionTempVariableRef
from nuitka.PythonVersions import python_version
from nuitka.utils.ModuleNames import ModuleName

from .FutureSpecState import enableFutureFeature, getFutureSpec
from .ReformulationTryFinallyStatements import makeTryFinallyReleaseStatement
from .SyntaxErrors import raiseSyntaxError
from .TreeHelpers import makeStatementsSequenceOrStatement, mangleName

# For checking afterwards, if __future__ imports really were at the beginning
# of the file.
_future_import_nodes = []


def checkFutureImportsOnlyAtStart(body):
    # Check if a __future__ imports really were at the beginning of the file.
    for node in body:
        if node in _future_import_nodes:
            _future_import_nodes.remove(node)
        else:
            if _future_import_nodes:
                raiseSyntaxError(
                    """\
from __future__ imports must occur at the beginning of the file""",
                    _future_import_nodes[0].source_ref.atColumnNumber(
                        _future_import_nodes[0].col_offset
                    ),
                )


def _handleFutureImport(provider, node, source_ref):
    # Don't allow future imports in functions or classes.
    if not provider.isCompiledPythonModule():
        raiseSyntaxError(
            """\
from __future__ imports must occur at the beginning of the file""",
            source_ref.atColumnNumber(node.col_offset),
        )

    for import_desc in node.names:
        object_name, _local_name = import_desc.name, import_desc.asname

        enableFutureFeature(node=node, object_name=object_name, source_ref=source_ref)

    # Remember it for checks to be applied once module is complete, e.g. if
    # they are all at module start.
    node.source_ref = source_ref
    _future_import_nodes.append(node)


def _resolveImportModuleName(module_name):
    if module_name:
        module_name = resolveModuleName(ModuleName(module_name)).asString()

    return module_name


def buildImportFromNode(provider, node, source_ref):
    # "from .. import .." statements. This may trigger a star import, or
    # multiple names being looked up from the given module variable name.
    # This is pretty complex.
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements

    module_name = node.module if node.module is not None else ""

    module_name = _resolveImportModuleName(module_name)

    level = node.level

    # Use default level under some circumstances.
    if level == -1:
        level = None
    elif level == 0 and not getFutureSpec().isAbsoluteImport():
        level = None

    if level is not None:
        level_obj = makeConstantRefNode(level, source_ref, True)
    else:
        level_obj = None

    # Importing from "__future__" module may enable flags to the parser,
    # that we need to know about, handle that.
    if module_name == "__future__":
        _handleFutureImport(provider, node, source_ref)

    target_names = []
    import_names = []

    # Mapping imported "fromlist" to assigned "fromlist" if any, handling the
    # star case as well.
    for import_desc in node.names:
        object_name, local_name = import_desc.name, import_desc.asname

        if object_name == "*":
            target_names.append(None)
            assert local_name is None
        else:
            target_names.append(local_name if local_name is not None else object_name)

        import_names.append(object_name)

    # Star imports get special treatment.
    if None in target_names:
        # More than "*" is a syntax error in Python, need not care about this at
        # all, it's only allowed value for import list in  this case.
        assert target_names == [None]

        # Python3 made it so that these can only occur on the module level,
        # so this a syntax error if not there. For Python2 it is OK to
        # occur everywhere though.
        if not provider.isCompiledPythonModule() and python_version >= 0x300:
            raiseSyntaxError(
                "import * only allowed at module level",
                source_ref.atColumnNumber(node.col_offset),
            )

        if provider.isCompiledPythonModule():
            import_globals = ExpressionBuiltinGlobals(source_ref)
            import_locals = ExpressionBuiltinGlobals(source_ref)
        else:
            import_globals = ExpressionBuiltinGlobals(source_ref)
            import_locals = makeConstantRefNode({}, source_ref, True)

        return StatementImportStar(
            target_scope=provider.getLocalsScope(),
            module=ExpressionBuiltinImport(
                name=makeConstantRefNode(module_name, source_ref, True),
                globals_arg=import_globals,
                locals_arg=import_locals,
                fromlist=makeConstantRefNode(("*",), source_ref, True),
                level=level_obj,
                source_ref=source_ref,
            ),
            source_ref=source_ref,
        )
    else:
        if module_name == "__future__":
            imported_from_module = makeExpressionImportModuleFixed(
                using_module_name=provider.getParentModule().getFullName(),
                module_name="__future__",
                value_name="__future__",
                source_ref=source_ref,
            )
        else:
            imported_from_module = ExpressionBuiltinImport(
                name=makeConstantRefNode(module_name, source_ref, True),
                globals_arg=ExpressionBuiltinGlobals(source_ref),
                locals_arg=makeConstantRefNode(None, source_ref, True),
                fromlist=makeConstantRefNode(tuple(import_names), source_ref, True),
                level=level_obj,
                source_ref=source_ref,
            )

        # If we have multiple names to import, consider each.
        multi_names = len(target_names) > 1

        statements = []

        if multi_names:
            tmp_import_from = provider.allocateTempVariable(
                temp_scope=provider.allocateTempScope("import_from"),
                name="module",
                temp_type="object",
            )

            statements.append(
                makeStatementAssignmentVariable(
                    variable=tmp_import_from,
                    source=imported_from_module,
                    source_ref=source_ref,
                )
            )

            imported_from_module = ExpressionTempVariableRef(
                variable=tmp_import_from, source_ref=source_ref
            )

        import_statements = []
        first = True

        for target_name, import_name in zip(target_names, import_names):
            # Make a clone of the variable reference, if we are going to use
            # another one.
            if not first:
                imported_from_module = imported_from_module.makeClone()
            first = False

            import_statements.append(
                StatementAssignmentVariableName(
                    provider=provider,
                    variable_name=mangleName(target_name, provider),
                    source=ExpressionImportName(
                        module=imported_from_module,
                        import_name=import_name,
                        level=0,
                        source_ref=source_ref,
                    ),
                    source_ref=source_ref,
                )
            )

        # Release the temporary module value as well.
        if multi_names:
            statements.append(
                makeTryFinallyReleaseStatement(
                    provider=provider,
                    tried=import_statements,
                    variables=(tmp_import_from,),
                    source_ref=source_ref,
                )
            )
        else:
            statements.extend(import_statements)

        # Note: Each import is sequential. It can succeed, and the failure of a
        # later one is not undoing previous ones. We can therefore have a
        # sequence of imports that each only import one thing therefore.
        return StatementsSequence(
            statements=mergeStatements(statements), source_ref=source_ref
        )


def buildImportModulesNode(provider, node, source_ref):
    # Import modules statement. As described in the Developer Manual, these
    # statements can be treated as several ones.

    import_names = [
        (import_desc.name, import_desc.asname) for import_desc in node.names
    ]

    import_nodes = []

    for import_desc in import_names:
        module_name, local_name = import_desc

        module_top_name = module_name.split(".")[0]

        # Note: The "level" of import is influenced by the future absolute
        # imports.
        level = (
            makeConstantRefNode(0, source_ref, True)
            if getFutureSpec().isAbsoluteImport()
            else None
        )

        module_name = _resolveImportModuleName(module_name)

        # TODO: Go to fixed node directly, avoiding the optimization for the
        # node to do it, with absolute imports we can use makeExpressionImportModuleFixed
        # instead.
        import_node = ExpressionBuiltinImport(
            name=makeConstantRefNode(module_name, source_ref, True),
            globals_arg=ExpressionBuiltinGlobals(source_ref),
            locals_arg=makeConstantRefNode(None, source_ref, True),
            fromlist=makeConstantRefNode(None, source_ref, True),
            level=level,
            source_ref=source_ref,
        )

        if local_name:
            # If is gets a local name, the real name must be used as a
            # temporary value only, being looked up recursively.
            for import_name in module_name.split(".")[1:]:
                import_node = ExpressionImportName(
                    module=import_node,
                    import_name=import_name,
                    # TODO: Does level make sense at all, should be removed.
                    level=0,
                    source_ref=source_ref,
                )

        # If a name was given, use the one provided, otherwise the import gives
        # the top level package name given for assignment of the imported
        # module.

        import_nodes.append(
            StatementAssignmentVariableName(
                provider=provider,
                variable_name=mangleName(
                    local_name if local_name is not None else module_top_name, provider
                ),
                source=import_node,
                source_ref=source_ref,
            )
        )

    # Note: Each import is sequential. It will potentially succeed, and the
    # failure of a later one is not changing that one bit . We can therefore
    # have a sequence of imports that only import one thing therefore.
    return makeStatementsSequenceOrStatement(
        statements=import_nodes, source_ref=source_ref
    )


#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
