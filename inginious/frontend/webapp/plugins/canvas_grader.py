import web
import logging
import requests
from collections import OrderedDict
from inginious.frontend.webapp.pages.course_admin.utils import INGIniousAdminPage

settings = None
course_factory = None

class CanvasGrader(INGIniousAdminPage):

    def GET_AUTH(self, courseid, taskid):
        course, task = self.get_course_and_check_rights(courseid, taskid)
        print("course: %s, task: %s" % (course, task))
        return self.page(course, task, [])

    def POST_AUTH(self, courseid, taskid):
        global settings
        course, task = self.get_course_and_check_rights(courseid, taskid)
        post_data = web.input()
        print("post_data: %s" % post_data)
        users = self.get_users_from_canvas(post_data.canvas_api_key, post_data.canvas_course_id)
        errors = []

        if len(users) == 0 and False:
            errors.append("Unable to retrieve student information from Canvas. Grades cannot be submitted. Check that the API key and Course ID are correct.")
            pass
        else:
            for key, value in post_data.items():
                if "user_" in key:
                    group_id = key.replace("user_", "")
                    usernames = group_id.split(",")

                    for username in usernames:
                        user_id = self.get_canvas_user_id(users, username)

                        if user_id == 0:
                            errors.append("Student %s was not found in grading book." % username)
                            logging.getLogger('inginious.webapp.plugin.canvas_grader').error("Student %s was not found in grading book." % username)
                            continue

                        grade = float(post_data["canvas_grade_" + group_id])
                        headers = {"Authorization":"Bearer " + post_data.canvas_api_key}
                        grade_url = "%s/api/v1/courses/%s/assignments/%s/submissions/%s" % (settings["canvas_url"], 
                                                                                            post_data.canvas_course_id,
                                                                                            post_data.canvas_assignment_id, 
                                                                                            user_id)
                        grade_data = {"comment[text_comment]":post_data["canvas_comments_" + group_id], 
                                        "submission[posted_grade]":str(grade)+"%"}
                        r = requests.put(grade_url, headers=headers, data=grade_data)

                        if r.status_code != 200:
                            errors.append("There was an error submitting a grade for user %s. Check the log files." % username)
                            logging.getLogger('inginious.webapp.plugin.canvas_grader').error("There was an error submitting a grade for user %s. API call: %s. Error message: %s" % (username, grade_url, r.text))

        return self.page(course, task, errors)

    def get_users_from_canvas(self, canvas_api_key, canvas_course_id):
        global settings
        headers = {"Authorization":"Bearer " + canvas_api_key}
        page = 1
        users = []

        while True:
            # sees that canvas caps per_page at 100, so no point in makigng it more]
            url = "%s/api/v1/courses/%i/enrollments?per_page=100&page=%i" % (settings["canvas_url"], int(canvas_course_id), page)
            r = requests.get(url, headers=headers)

            if r.status_code == 200:
                try:
                    users_page = r.json()
                    if len(users_page) == 0:
                        break
                    #print("printing users_page")
                    #print(users_page)
                    users += [{"id": x["user"]["id"], "login_id": x["user"]["sis_user_id"]} for x in users_page]
                    page += 1

                except ValueError as e:
                    users = []
                    logging.getLogger('inginious.webapp.plugin.canvas_grader').error("Error decoding JSON during user list request. Check that the API key and Course ID are correct.")
                    break
            else:
                users = []
                logging.getLogger('inginious.webapp.plugin.canvas_grader').error("None 200OK Response during user list request. Check that the API key and Course ID are correct.")
                break

        return users

    def get_canvas_user_id(self, canvas_users, username):
        global settings
        user_id = 0

        # Currently we rely on the idea that we can strip out a piece of the email to get the username
        for user in canvas_users:

            if user["login_id"].replace(settings["username_strip"], "") == username:
                user_id = user["id"]
                break

        return user_id

    def page(self, course, task, errors):
        global course_factory
        using_groups = course_factory._task_factory.get_task_descriptor_content(course.get_id(), task.get_id())["groups"]

        # get user list
        user_list = self.user_manager.get_course_registered_users(course, False)
        users = OrderedDict(sorted(list(self.user_manager.get_users_info(user_list).items()),
                                   key=lambda k: k[1][0] if k[1] is not None else ""))

        individual_results = list(self.database.user_tasks.find({"courseid": course.get_id(), "taskid": task.get_id(),
                                                                 "username": {"$in": user_list}}))

        # some data massaging
        individual_data = OrderedDict([(username, {"username": username, "realname": user[0] if user is not None else "",
                                                   "email": user[1] if user is not None else "",
                                                   "grade": 0, "status": "notviewed", "submissionid": 0})
                                       for username, user in users.items()])

        for user in individual_results:
            individual_data[user["username"]]["tried"] = user["tried"]
            individual_data[user["username"]]["submissionid"] = user["submissionid"]
            if user["tried"] == 0:
                individual_data[user["username"]]["status"] = "notattempted"
            elif user["succeeded"]:
                individual_data[user["username"]]["status"] = "succeeded"
            else:
                individual_data[user["username"]]["status"] = "failed"
            individual_data[user["username"]]["grade"] = user["grade"]

        student_data = individual_data.values()

        print("student_data: %s" % student_data)

        if using_groups:
            course_agg = self.database.aggregations.find_one({"courseid": course.get_id()})
            if "groups" in course_agg.keys():
                groups = course_agg["groups"]
                student_data = []
                users_by_group= []

                for i in groups:
                    group = []
                    for j in i["students"]:
                        for key, value in individual_data.items():
                            if key == j:
                                group.append(value)
                                individual_data.pop(key, None)
                                break

                    if(len(group) == 0):
                        continue

                    users_by_group.append(group)

                # we add all students not in a group to their own group for the purpose of grading
                for key, value in individual_data.items():
                    users_by_group.append([value])

                student_data = users_by_group

        comments = []
        if "course_comments" in settings:
            if course.get_id() in settings["course_comments"]:
                for i in settings["course_comments"][course.get_id()]:
                    comments.append([i, settings["course_comments"][course.get_id()][i]])

        return self.template_helper.get_renderer().course_admin.canvas_grader(course, task, student_data, using_groups, comments, errors)

def init(plugin_manager, _course_factory, client, plugin_config):
    """ Init the plugin """
    global settings
    global course_factory
    settings = plugin_config
    course_factory = _course_factory
    canvas_grader_pattern = settings.get("page_pattern", "external")
    #canvas_grader_pattern = r'/admin/canvas_grader/([^/]+)/([^/]+)'
    #canvas_grader_pattern = r'/admin/canvas_grader/'
    plugin_manager.add_page(canvas_grader_pattern, CanvasGrader)
