# Make sense of structs and generate c printf statements
import re
import os
import copy


def preprocess_c(lines):
    i = 0
    one_liners = []
    # macro key and data for later processing
    if_macros = {}
    define_macros = {}

    while i < len(lines):  # a simple - and incomplete - c preprocessor
        line = lines[i].strip()
        # preprocess comments
        ix = line.find("//")
        if ix > 0:  # ignore side comments
            line = line[:ix]
        if re.match(r"^//", line):  # skip line comments
            i += 1
            continue
        ix = line.find("/*")
        if ix > 0:  # ignore comments
            temp_line = line[:ix]  # in case the line contains something before the comment
            ix = -1
            while ix == -1:
                i += 1
                line = lines[i].strip()
                ix = line.find("*/")
            line = temp_line + " " + line[ix + 2:]
            line = line.strip()
        if len(line) == 0:
            i += 1
            continue
        # preprocess macros
        if re.match(r"^#define", line):
            macro_key = re.sub(r"#define *([a-z_A-Z0-0]\+)", r"\1", line)  # get the first word as the key
            macro = re.sub(r"#define *[a-z_A-Z0-9]*", "", line)  # get the rest
            if re.match(r"\\$", line):
                while re.match(r"\\$", line):
                    i += 1
                    assert (i < len(lines))  # multi-line macro started, it should end with a line without \ at the end
                    line = lines[i].strip()
                    macro += line[:-1] + " "  # macro line, omit \ char at the end
                i += 1
                macro += lines[i].strip()  # final #define macro line,
            define_macros[macro_key] = macro  # one lined define macro
            i += 1
            continue
        if re.match(r"^#if", line):  # store if macros to print and ignore TODO make sense of the if statements?
            key = line
            if_macros[key] = []
            while not re.match(r"^#endif", line):
                i += 1
                if i == len(lines):
                    break
                line = lines[i].strip()
                if_macros[key].append(line)
            i += 1
            continue
        current_line = line
        # print(line)
        # preprocess lines
        while not re.search(r"; *$", line) and not re.search(r"{ *$", line):
            i += 1
            if i == len(lines):
                break
            line = lines[i].strip()
            current_line += " " + line
        # print(current_line)
        one_liners.append(current_line)
        i += 1
    return one_liners, if_macros, define_macros


def read_c_variables(data="../data/c_struct", types=None):
    """ read the elements of a c struct and store them in a dictionary
    :param path: file that contains (only) the struct
    :return:
    """
    variables = {}
    if types is None:
        type_names = {"int": "int", "short": "short int", "long": "long int", "int64": "long int", "int32": "int",
                      "char": "char", "unsigned": "unsigned int",
                      "unsigned int": "unsigned int", "float": "float", "double": "double", "byte": "int"}
    else:
        type_names = copy.deepcopy(types)
    if isinstance(data, basestring):
        if os.path.isfile(data):
            with open(data, "r") as c_struct:
                lines = c_struct.read().splitlines()
        else:
            lines = data.splitlines()
    else:  # assume that the data is already in the desired format
        # print("data is a list")
        lines = data
    lines, if_macros, define_macros = preprocess_c(lines)
    functions = {}
    arrays = {}
    multi_pointers = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        ignore = True  # ignore anything that can not be interpreted
        if len(line) < 1 or re.search(r"[*][*]+", line):  # ignore pointers to multidimensional arrays for now
            i += 1
            multi_pointers.append(line)
            continue
        matched = re.search(r"(\([*][ ,\t]*[a-zA-Z_][_a-zA-Z0-9]*[ ,\t]*\))[^;]*;", line)  # ignore function pointers
        if matched:
            functions[matched.group(1)] = line
            i += 1
            continue
        matched = re.search(r"([a-zA-Z_][_a-zA-Z0-9]*[ ,\t]*\[)", line)  # ignore arrays
        if matched:
            arrays[matched.group(1)] = line
            i += 1
            continue
        # print(i, line)
        matched = re.match(r"[ ,\t]*(?:typedef)[ ,\t]*([^;]+)[ ,\t]*;", line)  # add typedef variable type names
        if matched:
            names = matched.group(1).split()
            type_names[names[-1].strip()] = " ".join(names[:-1])
            i += 1
            continue
        matched = re.match(r"[ ,\t]*struct[ ,\t]+([^;]+)[ ,\t]*;", line)  # add declared variables in a single line
        if matched:
            names = matched.group(1).split()
            var_type = names[0]
            for v in names[1:]:
                variables[v.strip(",")] = "struct " + var_type
            i += 1
            continue
        matched = re.match(r"[ ,\t]*([^;]+)[ ,\t]*;", line)
        if matched:  # add declared variables in a single line
            names = matched.group(1).split(",", 1)
            var_type = names[0]
            first_variable = var_type.split()[-1]
            var_type = " ".join(names[0].split()[:-1])
            if len(names) > 1:
                var_names = [first_variable] + names[1].split(",")
            else:
                var_names = [first_variable]
            for v in var_names:
                variables[v.strip()] = var_type
            i += 1
            continue
        matched = re.match(r"(?:typedef)*[ ,\t]*([^\{]+)[ ,\t]*\{$", line)  # add multi-line struct declarations
        if matched:
            key1 = matched.group(1).strip()
            key2 = None
            typedef_lines = []
            i += 1
            while i < len(lines):
                line = lines[i].strip()
                matched2 = re.search("}[ ,\t]*([a-zA-Z_][_a-zA-Z0-9]*)*[ ,\t]*;$", line)
                if matched2:
                    if matched2.group(1):
                        key2 = matched2.group(1).strip()
                    break
                typedef_lines.append(line)
                i += 1
            if re.match(r"(?:struct|enum)[ ,\t]*$", key1):
                if key2 is not None:
                    key1 = key2
            # print(key1, key2)
            type_names[key1] = key1
            variables[key1] = read_c_variables(data=typedef_lines, types=type_names)
            if key2 is not None:
                variables[key2] = variables[key1]
                type_names[key2] = key1
            i += 1
            continue
        # print("ignored " + line)
        i += 1
    return {"variables": variables, "type_names": type_names, "functions": functions, "arrays": arrays}


def print_arg(key):
    print_format = {"int": "%d", "long int": "%ld", "long long int": "%lld", "char": "%c", "unsigned": "%u",
                    "unsigned long": "%lu", "unsigned long int": "%lu", "byte": "%d", "short": "%d", "float": "%f",
                    "double": "%f", "uint16": "%u", "int64": "%ld", "signed int": "%d", "unsigned int": "%u"}
    return print_format.get(key.strip(), None)


def print_variable(var_dict, global_var_dict, explored_types, cprint="printf(", pad="", initial=None):
    c = '.'
    if initial is not None:
        if initial[0] == "*":
            print("%sif(%s){" % (pad, initial))
            c = '->'
            initial = initial.strip("*")
            pad += "\t"
    for k, v in var_dict["variables"].items():
        if isinstance(v, basestring) and v not in global_var_dict["variables"]:
            parg = print_arg(v.strip())
            if parg is None:  # can not find the correct format to print it
                # print("******************* warning %s can not be printed *********************************" % v.strip())
                continue
            if initial is None:
                print('%s%s" %s: %s,",%s)' % (pad, cprint, k, parg, k))
            else:
                if "*" in k:  # skip pointers for now?
                    # print("*%s%s%s: %s" % (initial, c, k.strip("*"), v.strip()))
                    # print('fprintf(stdout," *%s%s%s: %s,",*%s%s%s);' % (
                    #    initial, c, k.strip("*"), parg, initial, c, k.strip("*")))
                    continue
                else:
                    print('%s%s" %s%s%s: %s,",%s%s%s);' % (pad, cprint, initial, c, k, parg, initial, c, k))
        else:

            if k.strip()[0] == '*':
                initialed = '*' + initial.strip("*")
                key = k.strip()[1:]
            else:
                initialed = initial
                key = k.strip()
            if isinstance(v, basestring):
                if v.strip() in explored_types:
                    continue
                else:
                    explored_types.add(v.strip())
                print_variable(global_var_dict["variables"][v.strip()], global_var_dict, explored_types, pad=pad,
                               cprint=cprint, initial=initialed + c + key)
            else:
                print_variable(v, global_var_dict, explored_types, pad=pad, cprint=cprint, initial=initialed + c + key)
    if c == '->':
        print("%s}" % pad[:-1])


if __name__ == '__main__':
    var_dict = read_c_variables("../data/c_struct")

    # print(var_dict["variables"].items())
    print_variable(var_dict["variables"]["CrazyDude"], var_dict, explored_types=set(), cprint="fprintf(stdout,",
                   initial="*dude")
    print('fprintf(stdout,"\\n");')





"""def get_simple_attribute():
    pass


def get_complex_attribute():
    pass


def update_scope_delimiters(line, curly_brace, paranthesis, bracket):
    for c in line:
        if c == '{':
            curly_brace[0] += 1
        elif c == '(':
            paranthesis[0] += 1
        elif c == '[':
            bracket[0] += 1
        elif c == '}':
            curly_brace[1] += 1
        elif c == ')':
            paranthesis[1] += 1
        elif c == ')':
            bracket[1] += 1"""
