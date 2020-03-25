"""
Author:      XuLin Yang
Student id:  904904
Date:        2020-3-10 15:28:34
Description: main function
"""
import operator
from datetime import datetime
from mpi4py import MPI
from collections import Counter
import argparse
from LanguageSummary import LanguageSummary
from util import read_language_code, read_data_line_by_line, preprocess_data, dump_country_code_output, dump_hash_tag_output, dump_time, processing_data


def main(country_code_file_path, twitter_data_path):
    """
    :param country_code_file_path: the path of country_code_file
    :param twitter_data_path: the path of twitter_data
    """
    # initialize communicator
    comm = MPI.COMM_WORLD
    comm_rank = comm.Get_rank()
    comm_size = comm.Get_size()

    # the starting timestamp
    start = datetime.now()

    # read country_code info
    language_summary_dict = read_language_code(country_code_file_path)
    # TODO should language info in each process?
    dump_time(comm_rank, "reading country code file", datetime.now() - start)

    # counting hash_tag
    hash_tag_count = Counter()

    # only one processor, no need to split data
    if comm_size == 1:
        single_node_single_core_task(twitter_data_path, hash_tag_count, language_summary_dict, comm_rank)

    # multi processor
    else:
        # master processor split data to slave processors
        if comm_rank == 0:
            multi_core_master_processor_task(twitter_data_path, comm_size, comm, comm_rank)
        # slave processors receive data from master processor and summarize hash_tag and language
        else:
            multi_core_slave_processor_task(comm, hash_tag_count, language_summary_dict, comm_rank)

    # reduce LanguageSummary, hash_tag_count from slave processors to master processor
    reduced_language_summary_dict = comm.reduce(language_summary_dict, root=0, op=LanguageSummary.merge_language_list)
    reduced_hash_tag_count = comm.reduce(hash_tag_count, root=0, op=operator.add)

    # output summary in root process
    if comm_rank == 0:
        dumping_time_start = datetime.now()
        dump_hash_tag_output(reduced_hash_tag_count)
        dump_country_code_output(reduced_language_summary_dict.values())

        end = datetime.now()
        dump_time(comm_rank, "dumping output", end - dumping_time_start)
        program_run_time = end - start
        print("Programs runs {}(micro s)".format(program_run_time.microseconds))


def single_node_single_core_task(twitter_data_path, hash_tag_count, language_summary_dict, comm_rank):
    """
    :param twitter_data_path: the path of twitter_data
    :param hash_tag_count: Counter({hash_tag: int}) object
    :param language_summary_dict: {country_cde: LanguageSummary} object
    :param comm_rank: the rank of the current processor
    """
    line_count = 0
    for line in read_data_line_by_line(twitter_data_path):
        preprocessed_line = preprocess_data(line)
        # the line is data
        line_count += 1
        if preprocessed_line:
            processing_data(preprocessed_line, hash_tag_count, language_summary_dict)

    print("processor #{} processes {} lines.".format(comm_rank, line_count))


def multi_core_master_processor_task(twitter_data_path, comm_size, comm, comm_rank):
    """
    :param twitter_data_path: the path of twitter_data
    :param comm_size: number of working processors
    :param comm: communicator object
    :param comm_rank: the rank of the current processor
    """
    next_target = 1
    line_count = 0

    time_start = datetime.now()

    for line in read_data_line_by_line(twitter_data_path):
        preprocessed_line = preprocess_data(line)
        # the line is data
        line_count += 1
        if preprocessed_line:
            comm.send(preprocessed_line, next_target)
            # scatter data line by line to slave process
            next_target += 1
            if next_target == comm_size:
                next_target = 1

    # send None to slave processors to stop receiving
    for i in range(1, comm_size):
        comm.send(None, i)
    dump_time(comm_rank, "reading file", datetime.now() - time_start)
    print("processor #{} processes {} lines.".format(comm_rank, line_count))


def multi_core_slave_processor_task(comm, hash_tag_count, language_summary_dict, comm_rank):
    """
    :param comm: communicator object
    :param hash_tag_count: Counter({hash_tag: int}) object
    :param language_summary_dict: {country_cde: LanguageSummary} object
    :param comm_rank: the rank of the current processor
    """
    processing_time_start = datetime.now()
    recv_count = 0

    while True:
        local_preprocessed_line = comm.recv(source=0)
        # master processor has sent all data
        if not local_preprocessed_line:
            break
        recv_count += 1
        processing_data(local_preprocessed_line, hash_tag_count, language_summary_dict)

    dump_time(comm_rank, "processing", datetime.now() - processing_time_start)
    print("processor #{} recv {} lines.".format(comm_rank, recv_count))


if __name__ == "__main__":
    # Instantiate the parser
    parser = argparse.ArgumentParser(description='python to process data')
    # Required country code file
    parser.add_argument('-country', type=str, help='A required string path to country code file')
    # Required geo data path
    parser.add_argument('-data', type=str, help='A required string path to data file')
    args = parser.parse_args()

    country = args.country
    data = args.data

    main(country, data)
