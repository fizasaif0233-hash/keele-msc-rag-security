-- Allow the conventional RAG comparison. Chat sessions stay baseline or secured.

alter table public.experiments drop constraint if exists experiments_configuration_check;

alter table public.experiments
    add constraint experiments_configuration_check
    check (configuration in (
        'baseline',
        'secured',
        'permission_only',
        'prompt_separation_only',
        'redaction_only',
        'conventional'
    ));
