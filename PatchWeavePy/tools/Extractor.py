#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
import os
sys.path.append('./ast/')
from common.Utilities import error_exit, get_file_list, is_intersect, execute_command
import Emitter
import Logger
from ast import ASTGenerator
from common import Definitions, Values
import Converter
import Generator
import Finder
import collections


FILE_MACRO_DEF = Definitions.DIRECTORY_TMP + "/macro-def"


def extract_variable_name(source_path, start_pos, end_pos):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    start_line, start_column = start_pos
    end_line, end_column = end_pos
    if start_line != end_line:
        error_exit("LINE NOT SAME")
    source_line = ""
    if os.path.exists(source_path):
        with open(source_path, 'r') as source_file:
            content = source_file.readlines()
            source_line = str(content[start_line-1]).strip()

    var_name = source_line[start_column-3:end_column-2]
    return var_name.strip()


def extract_data_type_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    data_type_list = list()
    node_type = str(ast_node["type"])
    if "data_type" in ast_node.keys():
        data_type = str(ast_node['data_type'])
        data_type_list.append(data_type)
    if len(ast_node['children']) > 0:
        for child_node in ast_node['children']:
            child_data_type_list = extract_data_type_list(child_node)
            data_type_list = data_type_list + child_data_type_list
    return list(set(data_type_list))


def extract_source_list(trace_list):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\t\t\tcollecting source file list from trace ...")
    source_list = list()
    for trace_line in trace_list:
        source_path, line_number = str(trace_line).split(":")
        source_path = source_path.strip()
        if source_path not in source_list:
            source_list.append(source_path)
    return source_list


def extract_complete_function_node(function_def_node, source_path):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    # print(source_path)
    source_dir = "/".join(source_path.split("/")[:-1])
    # print(source_dir)
    if len(function_def_node['children']) > 1:
        source_file_loc = source_dir + "/" + function_def_node['file']
        # print(source_file_loc)
        source_file_loc = os.path.abspath(source_file_loc)
        # print(source_file_loc)
        return function_def_node, source_file_loc
    else:
        # header_file_loc = source_dir + "/" + function_def_node['file']
        header_file_loc = function_def_node['file']
        if str(header_file_loc).startswith("."):
            header_file_loc = source_dir + "/" + function_def_node['file']
        # print(header_file_loc)

        function_name = function_def_node['identifier']
        source_file_loc = header_file_loc.replace(".h", ".c")
        source_file_loc = os.path.abspath(source_file_loc)
        # print(source_file_loc)
        if not os.path.exists(source_file_loc):
            source_file_name = source_file_loc.split("/")[-1]
            header_file_dir = "/".join(source_file_loc.split("/")[:-1])
            search_dir = os.path.dirname(header_file_dir)
            while not os.path.exists(source_file_loc):
                search_dir_file_list = get_file_list(search_dir)
                for file_name in search_dir_file_list:
                    if source_file_name in file_name and file_name[-2:] == ".c":
                        source_file_loc = file_name
                        break
                if search_dir in [Values.PATH_A, Values.PATH_B, Values.PATH_C]:
                    return None, None
                search_dir = os.path.dirname(search_dir)

        ast_tree = ASTGenerator.get_ast_json(source_file_loc)
        function_node = Finder.search_function_node_by_name(ast_tree, function_name)
        return function_node, source_file_loc


def extract_child_id_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    id_list = list()
    for child_node in ast_node['children']:
        child_id = int(child_node['id'])
        id_list.append(child_id)
        grand_child_list = extract_child_id_list(child_node)
        if grand_child_list:
            id_list = id_list + grand_child_list
    if id_list:
        id_list = list(set(id_list))
    return id_list


def extract_call_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    call_expr_list = list()
    node_type = str(ast_node["type"])
    if node_type == "CallExpr":
        call_expr_list.append(ast_node)
    else:
        if len(ast_node['children']) > 0:
            for child_node in ast_node['children']:
                child_call_list = extract_call_node_list(child_node)
                call_expr_list = call_expr_list + child_call_list
    return call_expr_list


def extract_label_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    label_stmt_list = list()
    node_type = str(ast_node["type"])
    if node_type == "LabelStmt":
        label_stmt_list.append(ast_node)
    else:
        if len(ast_node['children']) > 0:
            for child_node in ast_node['children']:
                child_label_list = extract_label_node_list(child_node)
                call_expr_list = label_stmt_list + child_label_list
    return label_stmt_list


def extract_function_call_list(source_file, line_number):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    line_list = dict()
    ast_tree = ASTGenerator.get_ast_json(source_file)
    function_node = Finder.search_function_node_by_loc(ast_tree,
                                                       int(line_number),
                                                       source_file)
    if function_node is None:
        return line_list
    call_node_list = extract_call_node_list(function_node)

    for call_node in call_node_list:
        line_list[call_node['start line']] = call_node
    return line_list


def extract_var_dec_list(ast_node, start_line, end_line, only_in_range):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    var_list = list()
    child_count = len(ast_node['children'])
    node_start_line = int(ast_node['start line'])
    node_end_line = int(ast_node['end line'])
    start_column = int(ast_node['start column'])
    end_column = int(ast_node['end column'])
    node_type = ast_node['type']

    if only_in_range:
        if not is_intersect(node_start_line, node_end_line, start_line, end_line):
            return var_list

    if node_type in ["ParmVarDecl"]:
        var_name = str(ast_node['identifier'])
        var_type = str(ast_node['data_type'])
        line_number = int(ast_node['end line'])
        var_list.append((var_name, line_number, var_type))
        return var_list

    if node_type in ["VarDecl"]:
        child_count = len(ast_node['children'])
        if only_in_range and child_count < 2:
            return var_list
        var_name = str(ast_node['identifier'])
        var_type = str(ast_node['data_type'])
        line_number = int(ast_node['end line'])
        var_list.append((var_name, line_number, var_type))
        return var_list

    if child_count:
        for child_node in ast_node['children']:
            var_list = var_list + list(set(extract_var_dec_list(child_node, start_line, end_line, only_in_range)))
    return list(set(var_list))


def extract_return_line_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    return_line_list = list()
    child_count = len(ast_node['children'])
    node_type = ast_node['type']
    if node_type == "ReturnStmt":
        return_line_list.append(ast_node['start line'])
    else:
        if len(ast_node['children']) > 0:
            for child_node in ast_node['children']:
                child_return_list = extract_return_line_list(child_node)
                return_line_list = return_line_list + child_return_list
    return return_line_list


def extract_var_ref_list(ast_node, start_line, end_line, only_in_range):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    var_list = list()
    child_count = len(ast_node['children'])
    node_start_line = int(ast_node['start line'])
    node_end_line = int(ast_node['end line'])
    start_column = int(ast_node['start column'])
    end_column = int(ast_node['end column'])
    node_type = ast_node['type']
    if only_in_range:
        if not is_intersect(node_start_line, node_end_line, start_line, end_line):
            return var_list

    if node_type in ["ReturnStmt"]:
        return var_list
    if node_type == "BinaryOperator":
        insert_line_number = int(ast_node['end line'])
        node_value = ast_node['value']
        if node_value == "=":
            left_side = ast_node['children'][0]
            right_side = ast_node['children'][1]
            right_var_list = extract_var_ref_list(right_side, start_line, end_line, only_in_range)
            left_var_list = extract_var_ref_list(left_side, start_line, end_line, only_in_range)
            operands_var_list = right_var_list + left_var_list
            for var_name, line_number, var_type in operands_var_list:
                var_list.append((str(var_name), insert_line_number, str(var_type)))
            return var_list
    if node_type == "UnaryOperator":
        insert_line_number = int(ast_node['end line'])
        node_value = ast_node['value']
        if node_value == "&":
            child_node = ast_node['children'][0]
            child_var_list = extract_var_ref_list(child_node, start_line, end_line, only_in_range)
            for var_name, line_number, var_type in child_var_list:
                var_list.append(("&" + str(var_name), insert_line_number, var_type))
            return var_list
    if node_type == "DeclRefExpr":
        line_number = int(ast_node['start line'])
        if "ref_type" in ast_node.keys():
            ref_type = str(ast_node['ref_type'])
            if ref_type == "FunctionDecl":
                return var_list
        var_name = str(ast_node['value'])
        # print(ast_node)
        if 'data_type' in ast_node.keys():
            var_type = str(ast_node['data_type'])
        else:
            var_type = "macro"
        var_list.append((var_name, line_number, var_type))
    if node_type == "ArraySubscriptExpr":
        var_name, var_type, auxilary_list = Converter.convert_array_subscript(ast_node)
        line_number = int(ast_node['start line'])
        var_list.append((str(var_name), line_number, var_type))
        for aux_var_name, aux_var_type in auxilary_list:
            var_list.append((str(aux_var_name), line_number, aux_var_type))
        return var_list
    if node_type in ["MemberExpr"]:
        var_name, var_type, auxilary_list = Converter.convert_member_expr(ast_node)
        line_number = int(ast_node['start line'])
        var_list.append((str(var_name), line_number, var_type))
        for aux_var_name, aux_var_type in auxilary_list:
            var_list.append((str(aux_var_name), line_number, aux_var_type))
        return var_list
    if node_type in ["ForStmt", "WhileStmt"]:
        body_node = ast_node['children'][child_count - 1]
        insert_line = body_node['start line']
        for i in range(0, child_count - 1):
            condition_node = ast_node['children'][i]
            condition_node_var_list = extract_var_ref_list(condition_node, start_line, end_line, only_in_range)
            for var_name, line_number, var_type in condition_node_var_list:
                var_list.append((str(var_name), insert_line, var_type))
        var_list = var_list + extract_var_ref_list(body_node, start_line, end_line, only_in_range)
        return var_list
    # if node_type in ["CaseStmt"]:
    #     return var_list
    if node_type in ["IfStmt"]:
        condition_node = ast_node['children'][0]
        body_node = ast_node['children'][1]
        insert_line = body_node['start line']
        condition_node_var_list = extract_var_ref_list(condition_node, start_line, end_line, only_in_range)
        for var_name, line_number, var_type in condition_node_var_list:
            var_list.append((str(var_name), insert_line, var_type))
        var_list = var_list + extract_var_ref_list(body_node, start_line, end_line, only_in_range)
        return var_list
    if node_type in ["SwitchStmt"]:
        condition_node = ast_node['children'][0]
        body_node = ast_node['children'][1]
        insert_line = body_node['start line']
        condition_node_var_list = extract_var_ref_list(condition_node, start_line, end_line, only_in_range)
        for var_name, line_number, var_type in condition_node_var_list:
            var_list.append((str(var_name), insert_line, var_type))
        var_list = var_list + extract_var_ref_list(body_node, start_line, end_line, only_in_range)
        return var_list
    if node_type in ["CallExpr"]:
        line_number = ast_node['end line']
        if line_number <= end_line:
            for child_node in ast_node['children']:
                child_node_type = child_node['type']
                if child_node_type == "DeclRefExpr":
                    if "ref_type" in child_node.keys():
                        ref_type = child_node['ref_type']
                        if ref_type == "VarDecl":
                            var_name = str(child_node['value'])
                            # print(ast_node)
                            var_type = str(child_node['data_type'])
                            var_list.append((var_name, line_number, var_type))
                elif child_node_type == "MemberExpr":
                    var_name, var_type, auxilary_list = Converter.convert_member_expr(child_node)
                    var_list.append((str(var_name), line_number, var_type))
                    for aux_var_name, aux_var_type in auxilary_list:
                        var_list.append((str(aux_var_name), line_number, aux_var_type))
                elif child_node_type == "Macro":
                    var_name = str(child_node['value'])
                    if "?" in var_name:
                        continue
                    if "+" in var_name:
                        continue
                    var_type = "int"
                    var_list.append((str(var_name), line_number, var_type))
                else:
                    child_var_list = extract_var_ref_list(child_node, start_line, end_line, only_in_range)
                    for var_name, child_line, var_type in child_var_list:
                        var_list.append((var_name, line_number, var_type))
        return var_list
    if child_count:
        for child_node in ast_node['children']:
            var_list = var_list + list(set(extract_var_ref_list(child_node, start_line, end_line, only_in_range)))
    return list(set(var_list))


def extract_variable_list(source_path, start_line, end_line, only_in_range):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    # print(source_path, start_line, end_line)
    Emitter.normal("\t\t\t\tgenerating variable(available) list")
    variable_list = list()
    ast_map = ASTGenerator.get_ast_json(source_path)
    func_node = Finder.search_function_node_by_loc(ast_map, int(end_line), source_path)
    if func_node is None:
        return variable_list
    # print(source_path, start_line, end_line)
    compound_node = func_node['children'][1]
    if not only_in_range:
        param_node = func_node['children'][0]
        line_number = compound_node['start line']
        for child_node in param_node['children']:
            child_node_type = child_node['type']
            if child_node_type == "ParmVarDecl":
                var_name = str(child_node['identifier'])
                # print(child_node)
                var_type = str(child_node['data_type'])
                if var_name not in variable_list:
                    variable_list.append((var_name, line_number, var_type))

    for child_node in compound_node['children']:
        child_node_type = child_node['type']
        # print(child_node_type)
        child_node_start_line = int(child_node['start line'])
        child_node_end_line = int(child_node['end line'])
        filter_declarations = False
        # print(child_node_start_line, child_node_end_line)
        child_var_dec_list = extract_var_dec_list(child_node, start_line, end_line, only_in_range)
        # print(child_var_dec_list)
        child_var_ref_list = extract_var_ref_list(child_node, start_line, end_line, only_in_range)
        # print(child_var_ref_list)
        if child_node_start_line <= int(end_line) <= child_node_end_line:
            variable_list = list(set(variable_list + child_var_ref_list + child_var_dec_list))
            break
        #
        # if child_node_type in ["IfStmt", "ForStmt", "CaseStmt", "SwitchStmt", "DoStmt"]:
        #     # print("Inside")
        #     if not is_intersect(start_line, end_line, child_node_start_line, child_node_end_line):
        #         continue
        #     filter_var_ref_list = list()
        #     for var_ref in child_var_ref_list:
        #         if var_ref in child_var_dec_list:
        #             child_var_ref_list.remove(var_ref)
        #         elif "->" in var_ref:
        #             var_name = var_ref.split("->")[0]
        #             if var_name in child_var_dec_list:
        #                 filter_var_ref_list.append(var_ref)
        #     child_var_ref_list = list(set(child_var_ref_list) - set(filter_var_ref_list))
        #     variable_list = list(set(variable_list + child_var_ref_list))
        # else:
        variable_list = list(set(variable_list + child_var_ref_list + child_var_dec_list))
    # print(variable_list)
    filtered_list = list()
    # print(str(start_line), str(end_line))
    for var in variable_list:
        var_name, line_num, var_type = var
        if only_in_range:
            for dec_var in child_var_dec_list:
                dec_var_name, dec_line_num, dec_var_type = dec_var
                if dec_var_name == var_name:
                    continue
        if int(start_line) <= int(line_num) <= int(end_line):
            filtered_list.append(var)

    # print(variable_list)
    # print(filtered_list)
    return filtered_list


def extract_keys_from_model(model):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    byte_list = list()
    k_list = ""
    for dec in model:
        if hasattr(model[dec], "num_entries"):
            k_list = model[dec].as_list()
            if dec.name() == "A-data":
                break
    for pair in k_list:
        if type(pair) == list:
            byte_list.append(int(str(pair[0])))
    return byte_list


def extract_input_bytes_used(sym_expr):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    # print(sym_expr)
    model_a = ""
    try:
        model_a = Generator.generate_model(sym_expr)
    except Exception:
        # print(sym_expr)
        # print(Exception.message)
        Emitter.warning("\t\t\twarning: exception in generating model")
    # print("model-a")
    # print(model_a)
    input_byte_list = list()
    if model_a is not None:

        input_byte_list = extract_keys_from_model(model_a)
        if not input_byte_list:
            script_lines = str(sym_expr).split("\n")
            value_line = script_lines[3]
            if "A-data" in value_line:
                tokens = value_line.split("A-data")
                if len(tokens) > 2:
                    for token in tokens[1:]:
                        byte_index = ((token.split(")")[0]).split("bv")[1]).split(" ")[0]
                        input_byte_list.append(int(byte_index))
                    Emitter.warning("\t\t\twarning: manual inspection of bytes")
                elif len(tokens) == 2:
                    byte_index = ((tokens[1].split(")")[0]).split("bv")[1]).split(" ")[0]
                    input_byte_list.append(int(byte_index))
                else:
                   error_exit("unexpected error")
    # print("input byte list")
    # print(input_byte_list)
    if input_byte_list:
        input_byte_list.sort()

    return input_byte_list


def extract_common_bytes(bytes_a, bytes_c):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\tanalysing common bytes in symbolic paths")
    common_byte_list = list(set(bytes_a).intersection(bytes_c))
    return common_byte_list


def extract_divergent_point_list(list_trace_a, list_trace_b, path_a, path_b):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\textracting divergent point(s)")
    divergent_location_list = list()
    length_a = len(list_trace_a)
    length_b = len(list_trace_b)
    print(length_a, length_b)
    source_loc = ""
    gap = 0
    for i in range(0, length_a):
        trace_line_a = str(list_trace_a[i]).replace(path_a, "")
        found_diff = False
        if gap >= length_b - i:
            gap = 0;
        for j in range(i + gap, length_b):
            trace_line_b = str(list_trace_b[j]).replace(path_b, "")
            if trace_line_a == trace_line_b:
                break;
            elif found_diff:
                gap += 1;
            else:
                source_loc = list_trace_a[i]
                print("\t\tdivergent Point:\n\t\t " + source_loc)
                print(i, j, gap)
                print(trace_line_a, trace_line_b)
                divergent_location_list.append(source_loc)
                found_diff = True
    return divergent_location_list


def extract_declaration_line_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    line_list = list()
    child_count = len(ast_node['children'])
    node_start_line = int(ast_node['start line'])
    node_end_line = int(ast_node['end line'])
    start_column = int(ast_node['start column'])
    end_column = int(ast_node['end column'])
    node_type = ast_node['type']

    if node_type in ["VarDecl"]:
        line_list.append(node_start_line)
        return line_list

    if child_count:
        for child_node in ast_node['children']:
            line_list = line_list + list(set(extract_declaration_line_list(child_node)))
    return list(set(line_list))


def extract_macro_definitions(source_path):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\textracting macro definitions from\n\t\t" + str(source_path))
    extract_command = "clang -E -dD -dM " + source_path + " > " + FILE_MACRO_DEF
    execute_command(extract_command)
    with open(FILE_MACRO_DEF, "r") as macro_file:
        macro_def_list = macro_file.readlines()
        return macro_def_list


def extract_typedef_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    typedef_node_list = dict()
    node_type = str(ast_node["type"])
    if node_type in ["TypedefDecl"]:
        identifier = str(ast_node['identifier'])
        typedef_node_list[identifier] = ast_node

    if len(ast_node['children']) > 0:
        for child_node in ast_node['children']:
            child_typedef_node_list = extract_typedef_node_list(child_node)
            typedef_node_list.update(child_typedef_node_list)
    return typedef_node_list


def extract_function_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    function_node_list = dict()
    for child_node in ast_node['children']:
        node_type = str(child_node["type"])
        if node_type in ["FunctionDecl"]:
            identifier = str(child_node['identifier'])
            function_node_list[identifier] = child_node
    return function_node_list


def extract_typeloc_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    typeloc_node_list = dict()
    node_type = str(ast_node["type"])
    if node_type in ["TypeLoc"]:
        identifier = str(ast_node['value'])
        typeloc_node_list[identifier] = ast_node

    if len(ast_node['children']) > 0:
        for child_node in ast_node['children']:
            child_typeloc_node_list = extract_typeloc_node_list(child_node)
            # print(child_typeloc_node_list)
            typeloc_node_list.update(child_typeloc_node_list)
    return typeloc_node_list


def extract_decl_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    dec_list = list()
    node_type = str(ast_node["type"])
    if node_type in ["FunctionDecl", "VarDecl", "ParmVarDecl"]:
        identifier = str(ast_node['identifier'])
        dec_list.append(identifier)

    if len(ast_node['children']) > 0:
        for child_node in ast_node['children']:
            child_dec_list = extract_decl_list(child_node)
            dec_list = dec_list + child_dec_list
    return list(set(dec_list))


def extract_decl_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    dec_list = dict()
    node_type = str(ast_node["type"])
    if node_type in ["FunctionDecl", "VarDecl", "ParmVarDecl"]:
        identifier = str(ast_node['identifier'])
        dec_list[identifier] = ast_node

    if len(ast_node['children']) > 0:
        for child_node in ast_node['children']:
            child_dec_list = extract_decl_node_list(child_node)
            dec_list.update(child_dec_list)
    return dec_list


def extract_enum_node_list(ast_tree):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    dec_list = dict()
    node_type = str(ast_tree["type"])
    if node_type in ["EnumConstantDecl"]:
        identifier = str(ast_tree['identifier'])
        dec_list[identifier] = ast_tree

    if len(ast_tree['children']) > 0:
        for child_node in ast_tree['children']:
            child_dec_list = extract_enum_node_list(child_node)
            dec_list.update(child_dec_list)
    return dec_list


def extract_reference_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    ref_node_list = list()
    node_type = str(ast_node["type"])
    if node_type in ["Macro", "DeclRefExpr"]:
        ref_node_list.append(ast_node)
    else:
        if len(ast_node['children']) > 0:
            for child_node in ast_node['children']:
                child_ref_list = extract_reference_node_list(child_node)
                ref_node_list = ref_node_list + child_ref_list
    return ref_node_list


def extract_macro_node_list(ast_node):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    macro_node_list = list()
    node_type = str(ast_node["type"])
    if node_type in ["Macro"]:
        macro_node_list.append(ast_node)
    else:
        if len(ast_node['children']) > 0:
            for child_node in ast_node['children']:
                child_ref_list = extract_macro_node_list(child_node)
                macro_node_list = macro_node_list + child_ref_list
    return macro_node_list


def extract_unique_in_order(list):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    seen_set = set()
    seen_add = seen_set.add
    return [x for x in list if not (x in seen_set or seen_add(x))]


def extract_source_lines_from_trace(trace_list):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\t\t\t\textracting source lines executed ...")
    unique_trace_list = extract_unique_in_order(trace_list)
    # print(unique_trace_list)
    source_line_map = collections.OrderedDict()
    for trace_line in unique_trace_list:
        source_path, line_number = str(trace_line).split(":")
        if source_path not in source_line_map.keys():
            source_line_map[source_path] = list()
        source_line_map[source_path].append(int(line_number))
    return source_line_map


def extract_error_list_from_output(output):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    error_list = list()
    for output_line in output:
        if "runtime error" in output_line:
            error = "runtime error: "
            error += output_line.split(" runtime error: ")[1]
            error_list.append(error)
        elif "ERROR: AddressSanitizer" in output_line:
            error = "ERROR: "
            error += (output_line.split(" address ")[0]).split("ERROR: ")[1]
            error += " address"
            error_list.append(error)
    return error_list


def extract_macro_definition(ast_node, skip_line_list, source_file, target_file):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Emitter.normal("\t\t\t\textracting macro definitions")
    macro_list = dict()
    node_type = str(ast_node['type'])
    # print(ast_node)
    # print(node_type)
    if node_type == "Macro":
        identifier = str(ast_node['value'])
        # print(identifier)
        start_line = int(ast_node['start line'])
        if start_line in skip_line_list:
            return macro_list
        node_child_count = len(ast_node['children'])
        if identifier in Values.STANDARD_MACRO_LIST:
            return macro_list
        # print(node_child_count)
        if "(" in identifier:
            identifier = identifier.split("(")[0]
        if node_child_count > 0:
            for child_node in ast_node['children']:
                identifier = str(child_node['value'])
                # print(identifier)
                if str(identifier).isdigit():
                    continue
                if identifier in Values.STANDARD_MACRO_LIST:
                    continue
                if "(" in identifier:
                    identifier = identifier.split("(")[0]
                if identifier not in macro_list.keys():
                    info = dict()
                    info['source'] = source_file
                    info['target'] = target_file
                    macro_list[identifier] = info
                else:
                    info = macro_list[identifier]
                    if info['source'] != source_file or info['target'] != target_file:
                        error_exit("MACRO REQUIRED MULTIPLE TIMES!!")
        else:
            token_list = identifier.split(" ")
            # print(token_list)
            for token in token_list:
                if token in ["/", "+", "-"]:
                    continue
                if token not in macro_list.keys():
                    info = dict()
                    info['source'] = source_file
                    info['target'] = target_file
                    macro_list[token] = info
                else:
                    error_exit("MACRO REQUIRED MULTIPLE TIMES!!")
    return macro_list


def extract_project_path(source_path):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    if Values.PATH_A + "/" in source_path:
        return Values.PATH_A
    elif Values.PATH_B in source_path:
        return Values.PATH_B
    elif Values.PATH_C in source_path:
        return Values.PATH_C
