from django.contrib.auth.models import User, Group

from ecs.utils.testcases import EcsTestCase
from ecs.tasks.models import TaskType, Task

class AuthorizationTest(EcsTestCase):
    def setUp(self):
        group_a = Group.objects.create(name='group-a')
        group_b = Group.objects.create(name='group-b')
        self.user_a = User.objects.create(username='user-a')
        self.user_b = User.objects.create(username='user-b')
        self.user_c = User.objects.create(username='user-c')
        self.user_a.groups.add(group_a)
        self.user_b.groups.add(group_a, group_b)
        self.task_type_a = TaskType.objects.create(name='task-type-a')
        self.task_type_a.groups.add(group_a)
        self.task_type_b = TaskType.objects.create(name='task-type-b')
        self.task_type_b.groups.add(group_a, group_b)
        self.task_type_c = TaskType.objects.create(name='task-type-c')

    def test_simple_assignment(self):
        task = Task.objects.create(task_type=self.task_type_a)
        task.assign(self.user_a)
        task.assign(self.user_b)
        self.assertRaises(ValueError, task.assign, self.user_c)
        
        task = Task.objects.create(task_type=self.task_type_b)
        task.assign(self.user_a)
        task.assign(self.user_b)
        self.assertRaises(ValueError, task.assign, self.user_c)
        
        task = Task.objects.create(task_type=self.task_type_c)
        task.assign(self.user_a)
        task.assign(self.user_b)
        task.assign(self.user_c)
