# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2015 Université Catholique de Louvain.
#
# This file is part of INGInious.
#
# INGInious is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INGInious is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with INGInious.  If not, see <http://www.gnu.org/licenses/>.
""" Tasks' problems """
from abc import ABCMeta, abstractmethod
from random import shuffle

from common.base import id_checker
from common.tasks_code_boxes import InputBox, MultilineBox, TextBox, FileBox


class BasicProblem(object):
    """Basic problem """
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_type(self):
        """ Returns the type of the problem """
        return None

    @abstractmethod
    def input_is_consistent(self, task_input):
        """ Check if an input for this problem is consistent. Return true if this is case, false else """
        return False

    @abstractmethod
    def check_answer(self, task_input):
        """
            Check the answer. Returns four values:
            the first is either True, False or None, indicating respectively that the answer is valid, invalid, or need to be sent to VM
            the second is the error message assigned to the task, if any (unused for now)
            the third is the error message assigned to this problem, if any
            this fourth is the number of error if this problem is a multi-box problem. Must be an integer (0)
        """
        return True, None, None, 0

    def get_id(self):
        """ Get the id of this problem """
        return self._id

    def get_task(self):
        """ Get the task containing this problem """
        return self._task

    def get_name(self):
        """ Get the name of this problem """
        return self._name

    def get_header(self):
        """ Get the header of this problem """
        return self._header

    def get_original_content(self):
        """ Get a dict fully describing this sub-problem """
        return dict(self._original_content)

    def __init__(self, task, problemid, content):
        if not id_checker(problemid):
            raise Exception("Invalid problem _id: " + problemid)

        self._id = problemid
        self._task = task
        self._name = content['name'] if "name" in content else ""
        self._header = content['header'] if "header" in content else ""
        self._original_content = content


class MatchProblem(BasicProblem):
    """Display an input box and check that the content is correct"""

    def __init__(self, task, problemid, content):
        BasicProblem.__init__(self, task, problemid, content)
        if not "answer" in content:
            raise Exception("There is no answer in this problem with type==match")
        self._answer = str(content["answer"])

    def get_type(self):
        return "match"

    def input_is_consistent(self, task_input):
        return self.get_id() in task_input

    def check_answer(self, taskInput):
        if taskInput[self.get_id()].strip() == self._answer:
            return True, None, "Correct answer", 0
        else:
            return False, None, "Invalid answer", 0


class BasicCodeProblem(BasicProblem):
    """Basic problem with code input. Do all the job with the backend"""

    def __init__(self, task, problemid, content):
        BasicProblem.__init__(self, task, problemid, content)
        self._boxes = []
        if task.get_environment() is None:
            raise Exception("Environment undefined, but there is a problem with type=code or type=code-single-line")

    def get_boxes(self):
        """ Returns all the boxes of this code problem """
        return self._boxes

    @abstractmethod
    def get_type(self):
        return None

    def input_is_consistent(self, task_input):
        for box in self._boxes:
            if not box.input_is_consistent(task_input):
                return False
        return True

    _box_types = {"input-text": InputBox, "input-decimal": InputBox, "input-integer": InputBox, "multiline": MultilineBox, "text": TextBox,
                  "file": FileBox}

    def _create_box(self, boxid, box_content):
        """ Create adequate box """
        if not id_checker(boxid) and not boxid == "":
            raise Exception("Invalid box _id " + boxid)
        if "type" not in box_content:
            raise Exception("Box " + boxid + " does not have a type")
        try:
            return self._box_types[box_content["type"]](self, boxid, box_content)
        except:
            raise Exception("Unknow box type " + box_content["type"] + "for box _id " + boxid)

    def check_answer(self, _):
        return None, None, None, 0


class CodeSingleLineProblem(BasicCodeProblem):
    """Code problem with a single line of input"""

    def __init__(self, task, problemid, content):
        BasicCodeProblem.__init__(self, task, problemid, content)
        self._boxes = [self._create_box("", {"type": "input-text", "optional": content.get("optional", False)})]

    def get_type(self):
        return "code-single-line"


class CodeFileProblem(BasicCodeProblem):
    """Code problem which allow to test a file"""

    def __init__(self, task, problemid, content):
        BasicCodeProblem.__init__(self, task, problemid, content)
        self._boxes = [
            self._create_box("", {"type": "file", "max_size": content.get("max_size", None), "allowed_exts": content.get("allowed_exts", None)})]

    def get_type(self):
        return "code-file"


class CodeProblem(BasicCodeProblem):
    """Code problem"""

    def __init__(self, task, problemid, content):
        BasicCodeProblem.__init__(self, task, problemid, content)
        if "boxes" in content:
            self._boxes = []
            for boxid, box_content in content['boxes'].iteritems():
                if boxid == "":
                    raise Exception("Empty box ids are not allowed")
                self._boxes.append(self._create_box(boxid, box_content))
        else:
            if "language" in content:
                self._boxes = [self._create_box("", {"type": "multiline", "language": content["language"],
                                                     "optional": content.get("optional", False)})]
            else:
                self._boxes = [self._create_box("", {"type": "multiline", "optional": content.get("optional", False)})]

    def get_type(self):
        return "code"


class MultipleChoiceProblem(BasicProblem):
    """Multiple choice problems"""

    def __init__(self, task, problemid, content):
        BasicProblem.__init__(self, task, problemid, content)
        self._multiple = content.get("multiple", False)
        if "choices" not in content or not isinstance(content['choices'], list):
            raise Exception("Multiple choice problem " + problemid + " does not have choices or choices are not an array")
        good_choices = []
        bad_choices = []
        for index, choice in enumerate(content["choices"]):
            data = {"index": index}
            if "text" not in choice:
                raise Exception("A choice in " + problemid + " does not have text")
            data['text'] = choice["text"]
            if choice.get('valid', False):
                data['valid'] = True
                good_choices.append(data)
            else:
                data['valid'] = False
                bad_choices.append(data)

        if len(good_choices) == 0:
            raise Exception("Problem " + problemid + " does not have any valid answer")

        self._limit = 0
        if "limit" in content and isinstance(content['limit'], (int, long)) and content['limit'] >= 0 and content['limit'] >= len(good_choices):
            self._limit = content['limit']
        elif "limit" in content:
            raise Exception("Invalid limit in problem " + problemid)

        self._centralize = content.get("centralize", False)

        self._choices = good_choices + bad_choices
        shuffle(self._choices)

    def get_type(self):
        return "multiple-choice"

    def allow_multiple(self):
        """ Returns true if this multiple choice problem allows checking multiple answers """
        return self._multiple

    def get_choice_with_index(self, index):
        """ Return the choice with index=index """
        for entry in self._choices:
            if entry["index"] == index:
                return entry
        return None

    def input_is_consistent(self, task_input):
        if self.get_id() not in task_input:
            return False
        if self._multiple:
            if not isinstance(task_input[self.get_id()], list):
                return False
            try:  # test conversion to int
                for entry in task_input[self.get_id()]:
                    if self.get_choice_with_index(int(entry)) is None:
                        return False
            except ValueError:
                return False
        else:
            try:  # test conversion to int
                if self.get_choice_with_index(int(task_input[self.get_id()])) is None:
                    return False
            except ValueError:
                return False
        return True

    def check_answer(self, taskInput):
        valid = True
        if self._multiple:
            for choice in self._choices:
                if choice["valid"] and not choice["index"] in taskInput[self.get_id()] and not str(choice["index"]) in taskInput[self.get_id()]:
                    valid = False
                elif not choice["valid"] and (choice["index"] in taskInput[self.get_id()] or str(choice["index"]) in taskInput[self.get_id()]):
                    valid = False
        else:
            valid = self.get_choice_with_index(int(taskInput[self.get_id()]))["valid"]
        if not valid:
            if self._centralize:
                return False, None, None, 1
            else:
                return False, None, "Wrong answer. Make sure to select all the valid possibilities" if self._multiple else "Wrong answer", 1
        return True, None, None, 0
