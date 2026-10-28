-- DOMINIUM | Estoque diario da empresa (saldo SAP Utilizacao Livre).
-- Executar somente no Supabase haqzzxpocwzntyudrbch (projeto operacional).
-- Cada arquivo cria snapshot imutavel; sem atualizar Controle de Qualidade.
create table if not exists public.estoque_diario_importacoes (
    id uuid primary key default gen_random_uuid(),
    data_estoque date not null,
    nome_arquivo text not null check (length(nome_arquivo) between 1 and 180),
    hash_arquivo text not null check (hash_arquivo ~ '^[a-f0-9]{64}$'),
    linhas_origem integer not null check (linhas_origem > 0),
    materiais_distintos integer not null check (materiais_distintos > 0),
    quantidade_total numeric(20,3) not null check (quantidade_total >= 0),
    importado_por text not null check (length(importado_por) between 1 and 100),
    importado_em timestamptz not null default now(),
    unique (data_estoque, hash_arquivo)
);
create table if not exists public.estoque_diario_itens (
    importacao_id uuid not null references public.estoque_diario_importacoes(id) on delete restrict,
    material text not null check (material ~ '^[0-9]{1,32}$'),
    descricao_material text not null check (length(descricao_material) between 1 and 500),
    quantidade_livre numeric(20,3) not null check (quantidade_livre >= 0),
    primary key (importacao_id, material)
);
create index if not exists estoque_diario_importacoes_recente_idx
    on public.estoque_diario_importacoes (data_estoque desc, importado_em desc, id desc);
create index if not exists estoque_diario_itens_material_idx
    on public.estoque_diario_itens (material);
alter table public.estoque_diario_importacoes enable row level security;
alter table public.estoque_diario_itens enable row level security;
-- Somente o backend autentica o operador e usa a chave secreta do servidor.
revoke all on public.estoque_diario_importacoes from anon, authenticated, public;
revoke all on public.estoque_diario_itens from anon, authenticated, public;
grant select, insert on public.estoque_diario_importacoes to service_role;
grant select, insert on public.estoque_diario_itens to service_role;

create or replace function public.registrar_estoque_diario(
    p_data date, p_arquivo text, p_hash text, p_linhas integer,
    p_itens jsonb, p_operador text
) returns jsonb
language plpgsql security invoker
set search_path = ''
as $$
declare
    v_id uuid;
    v_item jsonb;
    v_material text;
    v_descricao text;
    v_quantidade numeric(20,3);
    v_total numeric(20,3) := 0;
    v_count integer := 0;
    v_existing record;
begin
    if p_data is null or p_data > (current_date + interval '1 day')::date
        or length(trim(coalesce(p_arquivo,''))) not between 1 and 180
        or coalesce(p_hash,'') !~ '^[a-f0-9]{64}$'
        or coalesce(p_linhas,0) not between 1 and 20000
        or length(trim(coalesce(p_operador,''))) not between 1 and 100
        or jsonb_typeof(p_itens) is distinct from 'array'
        or jsonb_array_length(p_itens) not between 1 and 10000
    then
        raise exception 'Dados da importacao invalidos';
    end if;
    select * into v_existing from public.estoque_diario_importacoes
     where data_estoque = p_data and hash_arquivo = p_hash;
    if found then
        return jsonb_build_object('ok',true,'repetido',true,'id',v_existing.id,
            'materiais',v_existing.materiais_distintos,'linhas',v_existing.linhas_origem,
            'quantidade_total',v_existing.quantidade_total);
    end if;
    -- Validacao completa antes da criacao do snapshot.
    for v_item in select value from jsonb_array_elements(p_itens)
    loop
        v_material := trim(v_item->>'material');
        v_descricao := trim(v_item->>'descricao_material');
        if v_material !~ '^[0-9]{1,32}$' or length(v_descricao) not between 1 and 500
           or jsonb_typeof(v_item->'quantidade_livre') not in ('number','string') then
            raise exception 'Material, descricao ou quantidade invalidos';
        end if;
        begin
            v_quantidade := (v_item->>'quantidade_livre')::numeric(20,3);
        exception when others then
            raise exception 'Quantidade invalida no arquivo';
        end;
        if v_quantidade < 0 or v_quantidade > 999999999999 then
            raise exception 'Quantidade fora do limite';
        end if;
        v_count := v_count + 1;
        v_total := v_total + v_quantidade;
    end loop;
    insert into public.estoque_diario_importacoes
      (data_estoque,nome_arquivo,hash_arquivo,linhas_origem,materiais_distintos,quantidade_total,importado_por)
    values (p_data,trim(p_arquivo),p_hash,p_linhas,v_count,v_total,trim(p_operador))
    returning id into v_id;
    insert into public.estoque_diario_itens(importacao_id,material,descricao_material,quantidade_livre)
       select v_id,trim(t.material),trim(t.descricao_material),t.quantidade_livre
         from jsonb_to_recordset(p_itens) as t(material text,descricao_material text,quantidade_livre numeric);
    -- PK impede materiais duplicados, e a funcao inteira e atomica.
    return jsonb_build_object('ok',true,'repetido',false,'id',v_id,
        'materiais',v_count,'linhas',p_linhas,'quantidade_total',v_total);
end;
$$;
revoke all on function public.registrar_estoque_diario(date,text,text,integer,jsonb,text) from public, anon, authenticated;
grant execute on function public.registrar_estoque_diario(date,text,text,integer,jsonb,text) to service_role;
comment on table public.estoque_diario_importacoes is 'Historico de cada importacao do estoque SAP por data; imutavel.';
comment on table public.estoque_diario_itens is 'Saldo Utilizacao Livre agregado por material em cada snapshot.';
