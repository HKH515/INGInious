from modules.base import renderer
from modules.login import loginInstance
from modules.courses import Course

#Course page
class CoursePage:
    #Simply display the page
    def GET(self,courseId):
        if loginInstance.isLoggedIn():
            #try: #TODO:enable
                course = Course(courseId)
                return renderer.course(course)
            #except:
            #    return renderer.error404()
        else:
            return renderer.index(False)