"""Process entry point for local browser exports; receives a task id, never code."""
import sys
from .local_tasks import Progress, Cancelled


def main(identifier):
    task = Progress(identifier)
    try:
        from .render import render_performance, preview_scene, export_build
        task.update('Opening studio')
        fn = {'performance': render_performance, 'scene_preview': preview_scene, 'build_export': export_build}[task.record['kind']]
        result = fn(task.record['payload'], task)
        task.check()
        task.finish('done', result=result, stage='Complete')
    except Cancelled:
        task.finish('cancelled', stage='Cancelled')
    except Exception as error:
        task.finish('error', error=str(error)[:1500], stage='Failed')


if __name__ == '__main__':
    main(sys.argv[1])
