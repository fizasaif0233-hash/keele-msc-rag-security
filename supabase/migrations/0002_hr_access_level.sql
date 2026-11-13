-- Allow the HR access level on documents that were created before it existed.

alter table public.documents drop constraint if exists documents_access_level_check;

alter table public.documents
    add constraint documents_access_level_check
    check (access_level in ('public', 'employee', 'hr', 'confidential', 'admin'));
