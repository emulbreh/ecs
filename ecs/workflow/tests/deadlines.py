from datetime import timedelta
from django.db import models
from django.contrib.contenttypes.models import ContentType

from ecs.workflow.tests.base import WorkflowTestCase
from ecs.workflow.models import Graph, Node, NodeType, Guard
from ecs import workflow
# test only models:
from ecs.workflow.models import Foo

from ecs.workflow.tests import deadline_declarations

class DeadlineTest(WorkflowTestCase):
    def setUp(self):
        super(DeadlineTest, self).setUp()
        self.foo_ct = ContentType.objects.get_for_model(Foo)
        
    def test_simple_deadline(self):
        g = Graph.objects.create(name='TestGraph', content_type=self.foo_ct, auto_start=True)
        n_a = g.create_node(deadline_declarations.A, start=True)
        n_b = g.create_node(deadline_declarations.B, end=True)
        n_c = g.create_node(deadline_declarations.C, end=True)
        n_a.add_edge(n_b)
        n_a.add_edge(n_c, deadline=True)
        
        # a, b
        obj = Foo.objects.create()
        
        self.assertActivitiesEqual(obj, [deadline_declarations.A])
        obj.workflow.do(deadline_declarations.A)
        
        self.assertActivitiesEqual(obj, [deadline_declarations.B])
        obj.workflow.do(deadline_declarations.B)
        
        self.assertActivitiesEqual(obj, [])
        
        # a[deadline], c
        
        obj = Foo.objects.create()
        self.assertActivitiesEqual(obj, [deadline_declarations.A])
        token = obj.workflow.activitiy_tokens[0]
        token.handle_deadline()
        
        self.assertActivitiesEqual(obj, [deadline_declarations.C])
        obj.workflow.do(deadline_declarations.C)
        
        self.assertActivitiesEqual(obj, [])

