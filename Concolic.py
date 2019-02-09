#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import sys, os
sys.path.append('./ast/')
import time
from Utilities import execute_command, error_exit, extract_bitcode
import Output
import Common
import Logger
import Differ
import Builder
from six.moves import cStringIO
from pysmt.smtlib.parser import SmtLibParser
from pysmt.shortcuts import get_model
import Generator
import Tracer
import Mapper


SYMBOLIC_CONVERTER = "gen-bout"
SYMBOLIC_ENGINE = "klee "
SYMBOLIC_ARGUMENTS_FOR_PATH = "-print-path  -write-smt2s  --libc=uclibc --posix-runtime --external-calls=all --only-replay-seeds --seed-out=$KTEST"
SYMBOLIC_ARGUMENTS_FOR_EXPR = "-no-exit-on-error --resolve-path --libc=uclibc --posix-runtime --external-calls=all --only-replay-seeds --seed-out=$KTEST"

VALUE_BIT_SIZE = 0
VALUE_BINARY_PATH_A = ""
VALUE_BINARY_PATH_B = ""
VALUE_BINARY_PATH_C = ""

FILE_KLEE_LOG_A = Common.DIRECTORY_OUTPUT + "/log-klee-pa"
FILE_KLEE_LOG_B = Common.DIRECTORY_OUTPUT + "/log-klee-pb"
FILE_KLEE_LOG_C = Common.DIRECTORY_OUTPUT + "/log-klee-pc"


FILE_SYM_PATH_A = Common.DIRECTORY_OUTPUT + "/sym-path-a"
FILE_SYM_PATH_B = Common.DIRECTORY_OUTPUT + "/sym-path-b"
FILE_SYM_PATH_C = Common.DIRECTORY_OUTPUT + "/sym-path-c"

FILE_SYMBOLIC_POC = Common.DIRECTORY_OUTPUT + "/symbolic.ktest"

sym_path_a = dict()
sym_path_b = dict()
sym_path_c = dict()


estimate_loc_map = dict()


def collect_symbolic_path(file_path, project_path):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Output.normal("\tcollecting symbolic path conditions")
    constraints = dict()
    if os.path.exists(file_path):
        source_path = ""
        path_condition = ""
        with open(file_path, 'r') as trace_file:
            for line in trace_file:
                if '[path:condition]' in line:
                    if project_path in line:
                        source_path = str(line.replace("[path:condition]", '')).split(" : ")[0]
                        source_path = source_path.strip()
                        source_path = os.path.abspath(source_path)
                        path_condition = str(line.replace("[path:condition]", '')).split(" : ")[1]
                        continue
                if source_path:
                    if "(exit)" not in line:
                        path_condition = path_condition + line
                    else:
                        constraints[source_path] = path_condition
                        source_path = ""
                        path_condition = ""
    return constraints


def generate_path_condition(binary_arguments, binary_path, binary_name, log_path):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Output.normal("\tgenerating symbolic trace for path conditions")
    trace_command = "cd " + binary_path + ";"
    sym_args = SYMBOLIC_ARGUMENTS_FOR_PATH
    trace_command += SYMBOLIC_ENGINE + sym_args.replace("$KTEST", FILE_SYMBOLIC_POC) + " " + binary_name + ".bc "\
                     + binary_arguments.replace("$POC", "A") + " --sym-files 1 " + str(VALUE_BIT_SIZE) + "  > " + log_path + \
                    " 2>&1"
    # print(trace_command)
    execute_command(trace_command)
    sym_file_path = binary_path + "/klee-last/test000001.smt2 "
    return sym_file_path


def generate_var_expressions(binary_arguments, binary_path, binary_name, log_path, indent=False):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    if indent:
        Output.normal("\t\tgenerating symbolic expressions")
    else:
        Output.normal("\t\t\tgenerating symbolic expressions")
    trace_command = "cd " + binary_path + ";"
    sym_args = SYMBOLIC_ARGUMENTS_FOR_EXPR
    trace_command += SYMBOLIC_ENGINE + sym_args.replace("$KTEST", FILE_SYMBOLIC_POC) + " " + binary_name + ".bc "\
                     + binary_arguments.replace("$POC", "A") + " --sym-files 1 " + str(VALUE_BIT_SIZE) + "  > " + log_path + \
                    " 2>&1"
    # print(trace_command)
    ret_code = execute_command(trace_command)
    if int(ret_code) != 0:
        error_exit("CONCOLIC EXECUTION FAILED with code " + ret_code)


def generate_trace_donor():
    global sym_path_a, sym_path_b
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Output.normal(Common.VALUE_PATH_A)
    if not Common.NO_SYM_TRACE_GEN:
        binary_path, binary_name = extract_bitcode(Common.VALUE_PATH_A + Common.VALUE_EXPLOIT_A.split(" ")[0])
        sym_file_path = generate_path_condition(" ".join(Common.VALUE_EXPLOIT_A.split(" ")[1:]), binary_path, binary_name, FILE_KLEE_LOG_A)
        copy_command = "cp " + sym_file_path + " " + FILE_SYM_PATH_A
        execute_command(copy_command)
    sym_path_a = collect_symbolic_path(FILE_KLEE_LOG_A, Common.VALUE_PATH_A)

    Output.normal(Common.VALUE_PATH_B)
    if not Common.NO_SYM_TRACE_GEN:
        binary_path, binary_name = extract_bitcode(Common.VALUE_PATH_B + Common.VALUE_EXPLOIT_A.split(" ")[0])
        sym_file_path = generate_path_condition(" ".join(Common.VALUE_EXPLOIT_A.split(" ")[1:]), binary_path, binary_name, FILE_KLEE_LOG_B)
        copy_command = "cp " + sym_file_path + " " + FILE_SYM_PATH_B
        execute_command(copy_command)
    sym_path_b = collect_symbolic_path(FILE_KLEE_LOG_B, Common.VALUE_PATH_B)


def generate_trace_target():
    global sym_path_c
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Output.normal(Common.VALUE_PATH_C)
    if not Common.NO_SYM_TRACE_GEN:
        binary_path, binary_name = extract_bitcode(Common.VALUE_PATH_C + Common.VALUE_EXPLOIT_C.split(" ")[0])
        sym_file_path = generate_path_condition(" ".join(Common.VALUE_EXPLOIT_C.split(" ")[1:]), binary_path, binary_name, FILE_KLEE_LOG_C)
        copy_command = "cp " + sym_file_path + " " + FILE_SYM_PATH_C
        execute_command(copy_command)
    sym_path_c = collect_symbolic_path(FILE_KLEE_LOG_C, Common.VALUE_PATH_C)


def convert_poc():
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    global VALUE_BIT_SIZE
    Output.normal("converting concrete poc to symbolic file")
    concrete_file = open(Common.VALUE_PATH_POC,'rb')
    VALUE_BIT_SIZE = os.fstat(concrete_file.fileno()).st_size
    convert_command = SYMBOLIC_CONVERTER + " --sym-file " + Common.VALUE_PATH_POC
    execute_command(convert_command)
    move_command = "mv file.bout " + FILE_SYMBOLIC_POC
    execute_command(move_command)


def safe_exec(function_def, title, *args):
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    start_time = time.time()
    Output.sub_title("starting " + title + "...")
    description = title[0].lower() + title[1:]
    try:
        Logger.information("running " + str(function_def))
        if not args:
            result = function_def()
        else:
            result = function_def(*args)
        duration = str(time.time() - start_time)
        Output.success("\n\tSuccessful " + description + ", after " + duration + " seconds.")
    except Exception as exception:
        duration = str(time.time() - start_time)
        Output.error("Crash during " + description + ", after " + duration + " seconds.")
        error_exit(exception, "Unexpected error during " + description + ".")
    return result


def execute():
    Logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    Output.title("Concolic execution traces")
    convert_poc()
    safe_exec(generate_trace_donor, "generating symbolic trace information from donor program")
    safe_exec(generate_trace_target, "generating symbolic trace information from target program")
