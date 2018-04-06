#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import absolute_import, division, print_function
from builtins import *
import argparse
import re

from amr_utils import *

'''Script that removes variables from AMR by duplicating the information, possibly deletes wiki-links
   Presupposes that files have a certain extension (default .txt)

   Sample input:

   # ::snt Bob likes himself.

   (l / like
		:ARG0 (p / person :name "Bob")
		:ARG1 p)

	Output *.tf:

	(like :ARG0 (person :name "Bob") :ARG1 (person :name "Bob"))

	Output *.sent:

	Bob likes himself.'''


def create_args_parser():
    '''Creating arg parser'''

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", required=True,
                        type=str, help="AMR file")
    parser.add_argument('-output_ext', required=False,
                        default='.tf', help="extension of output AMR files (default .tf)")
    parser.add_argument('-sent_ext', required=False,
                        default='.sent', help="extension of sentences (default .sent)")
    parser.add_argument('-output_path', required=True, help="Output path")
    parser.add_argument('--proxy', action='store_true', help='If Proxy is enabled, the output is store in separate folders.')
    args = parser.parse_args()

    return args


def single_line_convert(lines, filter_str=None):
    '''Convert AMRs to a single line, ignoring lines that start with "# ::"'''

    all_amrs = []
    cur_amr = []
    sents = []
    skip = False
    for line in lines:
        if '::snt-type ' in line and filter_str:
            if '::snt-type ' + filter_str in line:
                skip = False
            else:
                skip = True
        if not skip:
            if not line.strip() and cur_amr:
                cur_amr_line = " ".join(cur_amr)
                all_amrs.append(cur_amr_line.strip())
                cur_amr = []
            elif line.startswith('# ::snt') or line.startswith('# ::tok'):  # match sentence
                sent = re.sub('(^# ::(tok|snt))', '', line).strip()  # remove # ::snt or # ::tok
                sents.append(sent)
            elif not line.startswith('#'):
                cur_amr.append(line.strip())
        if not line.strip():
            skip = False
    if cur_amr:  # file did not end with newline, so add AMR here
        all_amrs.append(" ".join(cur_amr).strip())

    assert (len(all_amrs) == len(sents))  # sanity check

    return all_amrs, sents


def delete_wiki(f, filter_str=None):
    '''Delete wiki links from AMRs'''

    no_wiki = []
    skip = False
    for line in codecs.open(f, 'r', 'utf-8'):
        if '::snt-type ' in line and filter_str:
            if '::snt-type ' + filter_str in line:
                skip = False
            else:
                skip = True
        if not skip:
            n_line = re.sub(r':wiki "(.*?)"', '', line, 1)
            n_line = re.sub(':wiki -', '', n_line)
            no_wiki.append((len(n_line) - len(n_line.lstrip())) * ' ' + ' '.join(
                n_line.split()))  # convert double whitespace but keep leading whitespace
        if not line.strip():
            skip = False
    return no_wiki


def process_var_line(line, var_dict):
    '''Function that processes line with a variable in it. Returns the string without
       variables and the dictionary with var-name + var - value
       Only works if AMR is shown as multiple lines and input correctly!'''

    curr_var_name = False
    curr_var_value = False
    var_value = ''
    var_name = ''

    for idx, ch in enumerate(line):
        if ch == '/':  # we start adding the variable value
            curr_var_value = True
            curr_var_name = False
            var_value = ''
            continue

        if ch == '(':  # we start adding the variable name
            curr_var_name = True
            curr_var_value = False
            if var_value and var_name:  # we already found a name-value pair, add it now
                var_dict[var_name.strip()] = var_value.strip().replace(')', '').replace(' :name', '').replace(
                    ' :dayperiod', '').replace(' :mod', '')
            var_name = ''
            continue

        if curr_var_name:  # add to variable name
            var_name += ch
        if curr_var_value:  # add to variable value
            var_value += ch

    var_dict[var_name.strip()] = var_value.strip().replace(')', '')
    deleted_var_string = re.sub(r'\((.*?/)', '(', line).replace('( ', '(')  # delete variables from line

    return deleted_var_string, var_dict


def delete_amr_variables(amrs, filter_str=None):
    '''Function that deletes variables from AMRs'''

    var_dict = dict()
    del_amr = []
    skip = False
    for line in amrs:
        if '::snt-type ' in line and filter_str:
            if '::snt-type ' + filter_str in line:
                skip = False
            else:
                skip = True
        if not skip:
            if line.strip() and line[0] != '#':
                if '/' in line:  # variable here
                    deleted_var_string, var_dict = process_var_line(line, var_dict)  # process line and save variables
                    del_amr.append(deleted_var_string)  # save string with variables deleted

                else:  # (probable) reference to variable here!
                    split_line = line.split()
                    ref_var = split_line[1].replace(')', '')  # get var name

                    if ref_var in var_dict:
                        ref_value = var_dict[ref_var]  # value to replace the variable name with
                        split_line[1] = split_line[1].replace(ref_var,
                                                              '(' + ref_value.strip() + ')')  # do the replacing and add brackets for alignment
                        n_line = (len(line) - len(line.lstrip())) * ' ' + " ".join(split_line)
                        del_amr.append(n_line)
                    else:
                        del_amr.append(
                            line)  # no reference found, add line without editing (usually there are numbers in this line)
            else:
                del_amr.append(line)  # line with other info, just add
        if not line.strip():
            skip = False
    return del_amr


def gen_output(path, f, output_ext, sent_ext, filter_str=''):
    '''Generate output files'''
    amr_no_wiki = delete_wiki(f, filter_str)
    del_amrs = delete_amr_variables(amr_no_wiki, filter_str)
    single_amrs, sents = single_line_convert(del_amrs, filter_str)

    assert len(single_amrs) == len(sents)  # sanity check
    if filter_str:
        filter_name = filter_str + '_'
    else:
        filter_name = ''
    out_tf = os.path.join(path, filter_name + os.path.basename(f) + output_ext)
    out_sent = os.path.join(path, filter_name + os.path.basename(f) + sent_ext)
    write_to_file(single_amrs, out_tf)
    write_to_file(sents, out_sent)


def split_file(f):
    """
    Split AMR file into files respecting to each document ID
    """
    files = dict()
    store = ''
    file_id = ''
    for line in codecs.open(f, 'r', 'utf-8'):
        # Skip first line in file
        if line.startswith('# AMR'):
            continue
        # Save id
        if line.startswith('# ::id'):
            ids = line.split(' ')[2].split('.')
            file_id = ids[0]
        # Blank line and filled store
        if not line.strip() and store:
            store += '\n'
            assert file_id != ''
            files[file_id] = files.setdefault(file_id, '') + store
            store = ''
        # All lines that are not blank
        elif line.strip():
            store += line
    return files


if __name__ == "__main__":
    args = create_args_parser()

    print('Converting {0}...'.format(args.f))

    if not args.proxy:
        gen_output(args.output_path, args.f, args.output_ext, args.sent_ext, filter_str=None)
    else:
        # Create a folder specific for Proxy Report dataset
        proxy_path = os.path.join(args.output_path, 'proxy')
        if not os.path.exists(proxy_path):
            os.mkdir(proxy_path)

        # Create a folder for side-information input
        side_path = os.path.join(proxy_path, 'side')
        if not os.path.exists(side_path):
            os.mkdir(side_path)

        # Create a folder for no-side-information input
        no_side_path = os.path.join(proxy_path, 'no_side')
        if not os.path.exists(no_side_path):
            os.mkdir(no_side_path)

        '''
        No side folder
        '''
        gen_output(no_side_path, args.f, args.output_ext, args.sent_ext, filter_str='summary')

        '''
        Side folder
        '''
        # Write split files
        files = split_file(args.f)
        for file_id, lines in files.items():
            file_name = os.path.join(side_path, 'amr_' + file_id + '.txt')
            new_file = codecs.open(file_name, 'w', 'utf-8')
            new_file.write(lines)
            new_file.close()
            gen_output(side_path, file_name, args.output_ext, args.sent_ext, filter_str='body')
            gen_output(side_path, file_name, args.output_ext, args.sent_ext, filter_str='summary')


