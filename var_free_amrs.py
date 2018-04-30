#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import absolute_import, division, print_function
from builtins import *
import argparse
import re
import spacy
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
    parser.add_argument('--no_parentheses', action='store_true', help='Remove all parentheses.')
    parser.add_argument('--with_side', action='store_true', help='Generate a side or no side information folder structures.')
    parser.add_argument('--delete_amr_var', action='store_true', help='Delete the AMR variable.')
    parser.add_argument('--proxy', action='store_true', help='If Proxy is enabled, the output is store in separate folders.')
    parser.add_argument('--no_semantics', action='store_true', help='Remove all semantics identifier from the AMR concept nodes.')
    parser.add_argument('--filter_summary', action='store_true', help='Filter out non-summary in Proxy Report dataset of pre-training.')
    parser.add_argument('--custom_parentheses', action='store_true', help='Add extra space after all parentheses and remove beginning and ending parentheses.')
    args = parser.parse_args()

    return args


def single_line_convert(lines, filter_str=None):
    '''Convert AMRs to a single line, ignoring lines that start with "# ::"'''

    all_amrs = []
    cur_amr = []
    sents = []
    skip = False
    for line in lines:
        if line.startswith('# AMR'):
            continue
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
        if line.startswith('# AMR'):
            continue
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
        if line.startswith('# AMR'):
            continue
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


def post_process_line(args, single_amrs):
    new_lines = []
    for line in single_amrs:
        new_line = line
        if args.no_parentheses:
            new_line = re.sub(r'\(', '', new_line)
            new_line = re.sub(r'\)', '', new_line)
        else:
            if args.custom_parentheses:
                new_line = re.sub(r'\s\(', ' ( ', line)
                new_line = re.sub(r'^\(', '', new_line)

                new_line = re.sub(r'\)\s?', ' ) ', new_line)
                new_line = re.sub(r'\)\s$', '', new_line)
                new_line = re.sub(r'\s+', ' ', new_line)
        if args.no_semantics:
            new_line = re.sub(r'-[09]\d\s', ' ', new_line)
        new_lines.append(new_line)
    return new_lines


def gen_output(path, f, args, is_file=True, filter_str='', nlp=None):
    """
    Generate output in either file or dictionary format. Will automatically write to files.
    """
    output_ext = args.output_ext
    sent_ext = args.sent_ext
    amr_no_wiki = delete_wiki(f, filter_str)
    if args.delete_amr_var:
        amr_no_wiki = delete_amr_variables(amr_no_wiki, filter_str)
    single_amrs, sents = single_line_convert(amr_no_wiki, filter_str)
    tokenized_sents = []
    for sent in sents:
        doc = nlp.make_doc(sent)
        tokenized_sents.append(' '.join([token.text for token in doc]))
    single_amrs = post_process_line(args, single_amrs)

    assert len(single_amrs) == len(tokenized_sents)  # sanity check
    print('Number of sentence processed: {}'.format(len(single_amrs)))
    if filter_str:
        filter_name = filter_str + '_'
    else:
        filter_name = 'all_'
    if is_file:
        out_tf = os.path.join(path, filter_name + os.path.basename(f) + output_ext)
        out_sent = os.path.join(path, filter_name + os.path.basename(f) + sent_ext)
        write_to_file(single_amrs, out_tf)
        write_to_file(tokenized_sents, out_sent)
    else:
        result = dict()
        result[os.path.basename(f)] = (single_amrs, tokenized_sents)
        return result


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
    nlp = spacy.load('en')

    print('Converting {0}...'.format(args.f))

    if 'training' in args.f:
        split_path = 'training'
    elif 'test' in args.f:
        split_path = 'test'
    else:
        split_path = 'dev'

    filter_str = ''
    if args.with_side:
        if not os.path.exists(os.path.join(args.output_path, 'filter', split_path)):
            os.makedirs(os.path.join(args.output_path, 'filter', split_path))
        new_path = os.path.join(args.output_path, 'filter', split_path)
        filter_str = 'summary'
    else:
        if not os.path.exists(os.path.join(args.output_path, 'no_filter', split_path)):
            os.makedirs(os.path.join(args.output_path, 'no_filter', split_path))
        new_path = os.path.join(args.output_path, 'no_filter', split_path)

    if 'training' in new_path:
        gen_output(new_path, args.f, args, filter_str=filter_str, nlp=nlp)
    else:
        # Write split files
        files = split_file(args.f)
        body_result = dict()
        summary_result = dict()
        for file_id, lines in files.items():
            file_name = os.path.join(new_path, 'amr_' + file_id + '.txt')
            new_file = codecs.open(file_name, 'w', 'utf-8')
            new_file.write(lines)
            new_file.close()
            body_result.update(gen_output(new_path, file_name, args, is_file=False, filter_str='body', nlp=nlp))
            summary_result.update(gen_output(new_path, file_name, args, is_file=False, filter_str='summary', nlp=nlp))
            os.remove(file_name)
        assert body_result != None and summary_result != None
        # Join all body_result and summary_result into a single file
        single_body_amrs = []
        single_body_sents = []
        single_summ_amrs = []
        single_summ_sents = []
        for file_id, (summ_amrs, summ_sents) in summary_result.items():
            body_amrs, body_sents = body_result[file_id]
            assert len(summ_amrs) == len(summ_sents)
            for i in range(len(summ_sents)):
                single_summ_amrs.append(summ_amrs[i])
                single_summ_sents.append(summ_sents[i])
                a_body_amrs = ''
                for body_amr in body_amrs:
                    a_body_amrs = a_body_amrs + '<<sep>>' + body_amr
                single_body_amrs.append(a_body_amrs)
                single_body_sents.append(' '.join(body_sents))
        if args.with_side:
            out_tf = os.path.join(
                new_path,
                'body_' + os.path.basename(args.f) + args.output_ext)
            out_sent = os.path.join(
                new_path,
                'body_' + os.path.basename(args.f) + args.sent_ext)
            write_to_file(single_body_amrs, out_tf)
            write_to_file(single_body_sents, out_sent)
        out_tf = os.path.join(
            new_path,
            'summary_' + os.path.basename(args.f) + args.output_ext)
        out_sent = os.path.join(
            new_path,
            'summary_' + os.path.basename(args.f) + args.sent_ext)
        write_to_file(single_summ_amrs, out_tf)
        write_to_file(single_summ_sents, out_sent)

