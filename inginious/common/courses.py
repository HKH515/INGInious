# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Contains the class Course and utility functions """

import copy


class Course(object):
    """ Represents a course """

    def __init__(self, courseid, content_description, task_factory, hook_manager):
        """
        :param courseid: the course id
        :param content_description: a dict with all the infos of this course
        :param task_factory: a function with one argument, the task id, that returns a Task object
        """
        self._id = courseid
        self._content = content_description
        self._task_factory = task_factory
        self._hook_manager = hook_manager

    def get_id(self):
        """ Return the _id of this course """
        return self._id

    def get_task(self, taskid):
        """ Returns a Task object """
        return self._task_factory.get_task(self, taskid)

    def get_tasks(self):
        """ Get all tasks in this course """
        return self._task_factory.get_all_tasks(self)

    def get_descriptor(self):
        """ Get (a copy) the description of the course """
        return copy.deepcopy(self._content)
