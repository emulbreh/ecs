from django.conf import settings
from celery.decorators import task

from ecs.utils.testcases import EcsTestCase

@task()
def basic_test(**kwargs):
    logger = basic_test.get_logger(**kwargs)
    logger.info("celery is running task, we write to the celery logger, and by the way, CELERY_ALWAYS_EAGER is %s" % str(settings.CELERY_ALWAYS_EAGER))
    return 'success'

class CeleryTest(EcsTestCase):
    def test_celery(self):
        retval = basic_test.delay()
        self.failUnlessEqual(retval.get(), 'success')
        self.failUnlessEqual(retval.result, 'success')
        self.failUnless(retval.successful())

