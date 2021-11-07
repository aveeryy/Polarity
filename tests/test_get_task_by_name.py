from polarity.utils import get_task_by_name
from polarity.types.task import Task
import pytest


@pytest.mark.parametrize(
    'task_list,task_name',
    [
        ([Task('Patatas'), Task('Azúcar')], 'Patatas'),
        ([Task('Huevos')], 'Huevos'),
        ([Task('Huevos'), Task('Fideos'),
          Task('Sopa')], 'Fideos'),
        # Test for subtasks
        ([Task('Huevos', subtasks=[Task('Revolver los huevos')])
          ], 'Revolver los huevos'),
        # Test for deeply nested subtask
        ([
            Task('a',
                 subtasks=[
                     Task('b',
                          subtasks=[
                              Task('c',
                                   subtasks=[Task('d', subtasks=[Task('e')])])
                          ])
                 ])
        ], 'e')
    ])
def test_get_task_by_name(task_list: list[Task], task_name: str):
    assert get_task_by_name(task_list=task_list,
                            task_name=task_name).name == task_name
