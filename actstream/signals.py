from django.dispatch import Signal

action = Signal(providing_args=['verb', 'action_object', 'target',
                                'description', 'timestamp', 'batch_time_minutes', 'is_batchable', 'public'])
