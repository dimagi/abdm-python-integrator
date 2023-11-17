from celery import Task, shared_task


class PeriodicTask(Task):

    @classmethod
    def on_bound(cls, app):
        app.conf.beat_schedule[cls.name] = {
            'task': cls.name,
            'schedule': cls.run_every,
            'args': (),
            'kwargs': {},
            'options': cls.options or {}
        }


def periodic_task(**options):
    """Wrapper function to create periodic celery tasks using decorator.
        Parameters:
        queue (string): Name of the queue in which task is supposed to run
        run_every (integer|crontab): Accepts
            - integer value which represents the seconds interval in which task will run.
            - celery.schedules.crontab interval
        options (dict): https://docs.celeryq.dev/en/latest/reference/celery.app.task.html#celery.app.task.Task.apply_async # noqa E501
    """
    return _task(base=PeriodicTask, **options)


def _task(*args, **kwargs):
    """
    Wrapper function for shared_task that supports adding queue using the periodic_task decorator
    """
    kwargs.setdefault('options', {})
    if kwargs.get('base') == PeriodicTask:
        kwargs['options']['queue'] = kwargs.get('queue')

    def task(fn):
        return shared_task(*args, **kwargs)(fn)

    return task
