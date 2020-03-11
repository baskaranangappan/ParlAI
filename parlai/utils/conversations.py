#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Utility methods for conversations format.
"""
import datetime
import json
import os
import random


BAR = '=' * 60
SMALL_BAR = '-' * 60


class Metadata:
    """
    Utility class for conversation metadata.

    Metadata should be saved at <datapath>.metadata.
    """

    def __init__(self, datapath):
        self._load(datapath)

    def _load(self, datapath):
        self.metadata_path = self._get_path(datapath)
        if not os.path.isfile(self.metadata_path):
            raise RuntimeError(
                f'Metadata at path {self.metadata_path} not found. '
                'Double check your path.'
            )

        with open(self.metadata_path, 'rb') as f:
            metadata = json.load(f)

        self.datetime = metadata['date']
        self.opt = metadata['opt']
        self.self_chat = metadata['self_chat']
        self.speakers = metadata['speakers']
        self.version_num = metadata['version']
        self.extra_data = {}
        for k, v in metadata.items():
            if k not in ['date', 'opt', 'speakers', 'self_chat', 'version']:
                self.extra_data[k] = v

    def read(self):
        """
        Read the relevant metadata.
        """
        print(f'Metadata version {self.version_num}')
        print(f'Saved at: {self.datetime}')
        print(f'Self chat: {self.self_chat}')
        print(f'Speakers: {self.speakers}')
        print('Opt:')
        for k, v in self.opt.items():
            print(f'\t{k}: {v}')
        for k, v in self.extra_data.items():
            print(f'{k}: {v}')

    @staticmethod
    def _get_path(datapath):
        fle, _ = os.path.splitext(datapath)
        return fle + '.metadata'

    @staticmethod
    def version():
        return '0.1'

    @classmethod
    def save_metadata(
        cls, datapath, opt, self_chat=False, speakers=None, **kwargs,
    ):
        """
        Dump conversation metadata to file.
        """
        metadata = {}
        metadata['date'] = str(datetime.datetime.now())
        metadata['opt'] = opt
        metadata['self_chat'] = self_chat
        metadata['speakers'] = speakers
        metadata['version'] = cls.version()

        for k, v in kwargs.items():
            metadata[k] = v

        metadata_path = cls._get_path(datapath)
        print(f'[ Writing metadata to file {metadata_path} ]')
        with open(metadata_path, 'w') as f:
            f.write(json.dumps(metadata))


class Conversations:
    """
    Utility class for reading and writing from ParlAI Conversations format.

    Conversations should be saved in JSONL format, where each line is
    a JSON of the following form:
    {
        'possible_conversation_level_info': True,
        'dialog':
            [   [
                    {
                        'id': 'speaker_1',
                        'text': <first utterance>,
                    },
                    {
                        'id': 'speaker_2',
                        'text': <second utterance>,
                    },
                    ...
                ],
                ...
            ]
        ...
    }
    """

    def __init__(self, datapath):
        self.conversations = self._load_conversations(datapath)
        self.metadata = self._load_metadata(datapath)
        self.iterator_idx = 0

    @property
    def num_conversations(self):
        return len(self.conversations)

    def _load_conversations(self, datapath):
        if not os.path.isfile(datapath):
            raise RuntimeError(
                f'Conversations at path {datapath} not found. '
                'Double check your path.'
            )

        conversations = []
        with open(datapath, 'r') as f:
            lines = f.read().splitlines()
            for line in lines:
                conversations.append(json.loads(line))

        return conversations

    def _load_metadata(self, datapath):
        """
        Load metadata.

        Metadata should be saved at <identifier>.metadata
        Metadata should be of the following format:
        {
            'date': <date collected>,
            'opt': <opt used to collect the data,
            'speakers': <identity of speakers>,
            ...
            Other arguments.
        }
        """
        try:
            metadata = Metadata(datapath)
            return metadata
        except RuntimeError:
            print('Metadata does not exist. Please double check your datapath.')
            return None

    def read_metadata(self):
        if self.metadata is not None:
            self.metadata.read()

    def __getitem__(self, index):
        return self.conversations[index]

    def __next__(self):
        """
        Return the next conversation.
        """
        if self.iterator_idx >= self.num_conversations:
            print('You reached the end of the conversations.')
            self.reset()  # return the iterator idx to 0
            return None

        conv = self.conversations[self.iterator_idx]
        self.iterator_idx += 1

        return conv

    def read_conv_idx(self, idx):
        convo = self.conversations[idx]
        print(BAR)

        high_level = [k for k in convo.keys() if k != 'dialog']
        if high_level:
            for key in high_level:
                print(f'{key}: {convo[key]}')
            print(SMALL_BAR)

        for act_pair in convo['dialog']:
            for turn in act_pair:
                turn_id = turn['id']
                text = turn['text']
                print(f'{turn_id}: {text}')

        print(BAR)

    def read_rand_conv(self):
        idx = random.choice(range(self.num_conversations))
        self.read_conv_idx(idx)

    def reset(self):
        self.iterator_idx = 0

    @staticmethod
    def _get_path(datapath):
        fle, _ = os.path.splitext(datapath)
        return fle + '.jsonl'

    @classmethod
    def save_conversations(
        cls,
        act_list,
        datapath,
        opt,
        save_keys='text,labels,eval_labels',
        context_ids='context',
        self_chat=False,
        **kwargs,
    ):
        """
        Write Conversations to file from an act list.
        """
        to_save = cls._get_path(datapath)

        context_ids = context_ids.split(',')
        # save conversations
        speakers = []
        with open(to_save, 'w') as f:
            for ep in act_list:
                if not ep:
                    continue
                convo = {
                    'dialog': [],
                    'context': [],
                    'metadata_path': Metadata._get_path(to_save),
                }
                for act_pair in ep:
                    new_pair = []
                    for ex in act_pair:
                        ex_id = ex.get('id')
                        if ex_id in context_ids:
                            context = True
                        else:
                            context = False
                            if ex_id not in speakers:
                                speakers.append(ex_id)
                        # set turn
                        turn = {}
                        for key in save_keys.split(','):
                            turn[key] = ex.get(key, '')
                        turn['id'] = ex_id
                        if not context:
                            new_pair.append(turn)
                        else:
                            convo['context'].append(turn)
                    if new_pair:
                        convo['dialog'].append(new_pair)
                json_convo = json.dumps(convo)
                f.write(json_convo + '\n')
        print(f' [ Conversations saved to file: {to_save} ]')

        # save metadata
        Metadata.save_metadata(
            to_save, opt, self_chat=self_chat, speakers=speakers, **kwargs,
        )
