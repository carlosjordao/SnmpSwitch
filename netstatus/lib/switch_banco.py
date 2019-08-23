import re
from datetime import datetime

"""
   ip = ''
    alias = ''
    comum = {
         'nome':   {'valor':'', 'oid':'.1.3.6.1.2.1.1.5.0'}
        ,'descr':  {'valor':'', 'oid':'.1.3.6.1.2.1.1.1.0'}
        ,'mac':    {'valor':'', 'oid':'.1.3.6.1.2.1.17.1.1.0'}
        ,'stp':    {'valor':'', 'oid':'.1.3.6.1.2.1.17.2.7.0'}
    }
    caracteristicas = {
         'fisico': {'valor':'', 'oid':'.1.3.6.1.2.1.47.1.1.1.1.7.'}
        ,'versoft':{'valor':'', 'oid':'.1.3.6.1.2.1.47.1.1.1.1.10.'}
        ,'serial': {'valor':'', 'oid':'.1.3.6.1.2.1.47.1.1.1.1.11.'}
        ,'fab':    {'valor':'', 'oid':'.1.3.6.1.2.1.47.1.1.1.1.12.'}
        ,'modelo': {'valor':'', 'oid':'.1.3.6.1.2.1.47.1.1.1.1.13.'}
    }
"""
class SwitchBanco:
    # onde cada variável está localizada na classe Switch
    # mapeia para nomes locais que são equivalentes ao SQL.
    # regra: se for lista, então o atributo está dentro de um dict
    detalhes = {
         'nome': ['board', 'nome']
        ,'alias': "alias"
        ,'mac': ['board', 'mac']
        ,'ip': 'ip'
        ,'modelo':      ['board', 'modelo']
        ,'fabricante':  ['board', 'fab']
        ,'versao_soft': ['board', 'versoft']
        ,'stp_root':    ["board", 'stp']
        ,'community_ro': 'comunidade'
        ,'serial_number': ["board", 'serial']
    }

    # faz uma formatação para SQL. Ou seja, envolve strings entre aspas
    # e faz outras adaptações necessárias para um insert/update
    def _format_dict(self, arr):
        dados = {}
        for k,v in arr.items():
            if type(v) is str:
                tmp = "'" + v.replace("'","''") + "'"
            elif type(v) is list or type(v) is tuple:
                try:
                    tmp = "'" + ','.join(v) + "'"
                except:
                    print("conv: {}".format(v))
                    tmp = "','" + str(v) + "'"
            elif type(v) is int:
                tmp = str(v)
            else:
                # ignorar tipos desconhecidos
                continue
            dados[k] = tmp
        return dados


    # magicamente busca o atributo na classe Switch conforme a configuração
    # de mapeamento em 'detalhes'
    # retorna um dict de variáveis locais com valores de Switch
    def switch_data(self, switch):
        res = {}
        for k,v in self.detalhes.items():
            if type(v) is str:
                valor = getattr(switch,v)
            else:
                array, idx = v
                valor = getattr(switch, array)[idx]
            res[k] = valor
        return res


    # cria o SQL adequado para deixar apenas um IP ativo por switch.
    def switch_inconsistente(self, switch):
        dados = self.switch_data(switch)
        res = ("UPDATE switches SET status='inativo_script' WHERE status='ativo' AND ip='{}' and serial_number <> '{}';".format(dados['ip'], dados['serial_number']),) 
        return res

    # ---------------
    # funções principais, para gerarem SQL
    # - - - - - - - - -   - - - - - - -   - - - -
    # id            | integer               | not null default nextval('switches_id_seq'::regclass)
    # nome          | character varying(40) | not null
    # alias         | character varying(7)  | not null
    # mac           | character varying(17) | not null
    # ip            | character varying(15) | not null
    # modelo        | character varying(60) | 
    # serial_number | character varying(40) | not null
    # status        | inventario            | not null
    # fabricante    | character varying(30) | 
    # versao_soft   | character varying(80) | 
    # stp_root      | smallint              | 
    # community_ro  | character varying(20) | not null default 'public'::character varying
    # community_rw  | character varying(20) | not null default ''::character varying
    def insert(self, switch):
        res = ()
        sql = 'INSERT INTO switches '

        dados = self.switch_data(switch)
        sql_fields_names = ['id', 'status']
        sql_fields = ['default', "'ativo'"]

        for k, v in self._format_dict(dados).items():
            if k == 'alias' and len(v) > 7:
                if v == "'IQ.CORE-IQ.CORE'":
                    v = "'CORE-00'"
                else:
                    v = "'" + v[1:7] + "'"
                print('-- alias = ' + v + "\n")
            sql_fields_names += [k]
            sql_fields += [v]

        sql += '(' + ', '.join(sql_fields_names) + ') VALUES (' + ', '.join(sql_fields) + ')'
        print('-- {}\n'.format(sql))
        #pprint(dados)
        sql += ';'

        res += ("UPDATE switches SET status='inativo_script' WHERE status='ativo' AND ip='" + dados['ip']  + "';", 
                sql,
                )
        # para uso abaixo, no switches_portas
        sql_where = " WHERE serial_number='" + dados['serial_number'] + "'"

        for porta, arr in switch.portas.items():
            sql = 'INSERT INTO switches_portas '
            dados_portas = self._format_dict(arr)
            dados_portas['mac_count'] = '0'
            dados_portas['port'] = str(porta)
            dados_portas['nome'] = dados_portas['nome'][0:30]
            dados_portas['alias'] = dados_portas['alias'][0:80]
            agora = datetime.now()
            dados_portas['data'] = "'{}'".format(agora.strftime('%Y-%m-%d %H:%M:%S.%f'))
            dados_portas['switch'] = '(SELECT id FROM switches %s)' % (sql_where)

            sql_fields_names = []
            sql_fields = []
            for k, v in dados_portas.items():
                sql_fields_names += [k]
                sql_fields += [v]
            sql += '(' + ', '.join(sql_fields_names) + ') VALUES (' + ', '.join(sql_fields) + ')'
            sql += ';'

            res += (sql,)
        return res


    def update(self, switch):
        res = ()
        sql = 'UPDATE switches SET '

        dados = self.switch_data(switch)
        dados['status'] = "ativo"
        v = dados['alias']
        if len(v) > 7:
            if v == "IQ.CORE-IQ.CORE":
                v = "CORE-00"
            else:
                v = v[0:7]
            dados['alias'] = v

        sql += ', '.join((k + '=' + v for k, v in self._format_dict(dados).items()))
        #pprint(dados)
        sql_where = " WHERE serial_number='{}'".format(dados['serial_number'])
        sql += sql_where
        sql += ';'

        res += (sql,)

        for porta, arr in switch.portas.items():
            sql = 'UPDATE switches_portas SET '
            dados_portas = self._format_dict(arr)
            agora = datetime.now()
            dados_portas['data'] = "'{}'".format(agora.strftime('%Y-%m-%d %H:%M:%S.%f'))
            dados_portas['nome'] = dados_portas['nome'][0:30]
            if re.match('[0-9A-F]{2} [0-9A-F]{2} [0-9A-F]{2} [0-9A-F]{2}', dados_portas['alias']) is not None:
                dados_portas['alias'] = ''.join(dados_portas['alias'].decode('hex')).replace("''","'")
            dados_portas['alias'] = dados_portas['alias'][0:80]
 
            sql += ', '.join((k+'='+v for k,v in dados_portas.items()))
            sql += ' WHERE port=%d and switch = (SELECT id FROM switches %s)' % (porta, sql_where)
            sql += ';'

            res += (sql,)
        return res


    # carga do 7900.
    def update_ipmac(self, switch):
        return ("UPDATE mac SET ip='{}' WHERE mac='{}';".format(v, k) for k, v in switch.ip_mac.items()) if switch is not None else None


    # versão onde lista_macs é dict, e a chave é uma tupla, para evitar redundância
    # de dados entre switches
    def insert_macs(self, lista_macs):
        retorno = ()
        for (switch_id, mac, vlan), porta in lista_macs.items():
            agora = datetime.now()
            retorno += ("INSERT INTO tmp_mac VALUES ({}, '{}', {}, {}, '', '{}');".format(switch_id, mac, porta, vlan, agora.strftime('%Y-%m-%d %H:%M:%S.%f')),)

        if retorno:
            retorno += ("DELETE FROM mac; INSERT INTO mac SELECT * FROM tmp_mac; TRUNCATE tmp_mac;",)
        return retorno
  

    def insert_vizinhos(self, switch):
        mac = switch.board['mac']
        #retorno = ("DELETE FROM switches_vizinhos where mac1='{}';".format(mac),)
        retorno = ()
        for lporta in switch.uplink:
            omac, oporta = switch.lldp[lporta]
            retorno += ("INSERT INTO switches_vizinhos VALUES ('{}', {}, '{}', {});".format(mac, lporta, omac, oporta),)
        return retorno
