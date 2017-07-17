from jinja2 import Environment, FileSystemLoader, exceptions, Template
import odoorpc
from ConfigParser import ConfigParser
import yaml
import json
import os
import tempfile
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class Brouwseresult(type):
    def __new__(cls, name, parents, dct):
        return super(Brouwseresult, cls).__new__(cls, name, parents, dct)


class RPCmethods(object):
    def __init__(self, url=None, port=8069, username=None, password=None,
                 dbname=False, load_config='config.conf'):
        self.url = url
        self.uid = None
        self.username = username
        self.password = password
        self.dbname = dbname
        self.port = port
        self.conection = None
        self.config_file = load_config
        if load_config:
            self.get_config()

    def login(self):
        """
        Method connects to an instance of odoo
        return: None
        params: None
        """
        common = odoorpc.ODOO(self.url, port=self.port)
        common.login(self.dbname, self.username, self.password)
        self.uid = common.env.user.id
        self.conection = common

    def execute(self, model, method, params):
        """
        Method executes queries in odoo in a specific model
        using the already established connection.
        return: result of query
        model: string
        model: string
        params: list of tuples or dict
        """
        env = self.conection.env[model]
        result = getattr(env, method)(*params)
        return result

    def get_config(self):
        """
        Method opens a configuration file and assigns the values
        to the attributes of the class
        """
        config = ConfigParser()
        config.read(self.config_file)
        for key, value in config.items('LOGIN'):
            if hasattr(self, key):
                setattr(self, key, value)

    def query_load_data(self, model, search_args, values, write=False):
        """
        Method executes the search or creates in odoo,
        from the received data
        return: int
        model: string
        search_args: list of tuples
        values: dict
        """
        res_id = False
        if search_args:
            res_id = self.execute(model, 'search', (search_args,))
        if write and res_id:
            self.execute(model, 'write', (res_id, values))
        if not res_id and values:
            res_id = self.execute(model, 'create', (values,))
        return res_id


class Parserdata(object):

    def __init__(self, config_file):
        self.config_file = config_file
        self.data = self.load_data()

    def load_data(self):
        """
        Method opens an extension file yml
        """
        try:
            data = yaml.load(open(self.config_file).read())
        except yaml.error, error:
            raise error
        return data

    def create_tempfile(self, data):
        """
        Method creates a temporary file
        return: object temp fopen
        data: dict
        """
        tmp = tempfile.NamedTemporaryFile()
        file_dump = json.dumps(data)
        tmp.write(file_dump)
        tmp.seek(0)
        return tmp

    def render_depends_values(self, filters, data):
        """
        Method creates a template with the data and adds the filters to
        the template to then load the data corresponding to the process
        return: dict
        filters: list
        data: data
        """
        template = Template(json.dumps(data))
        update_template = {}
        for fill in filters:
            update_template.update({fill: self.data[fill].get("result")})
        result = yaml.load(template.render(update_template))
        return result

    def eval_parameters(self, parameter):
        """
        This method is used to evaluate the list of tuples that pass
        as a string and convert them into lists of real tuples
        parameter: string
        return: list of tuples
        """
        result = []
        for param in parameter:
            value = eval(param)
            field = value[0]
            oper = value[1]
            val = int(value[2]) if value[2].isdigit() else value[2]
            value = (field, oper, val)
            result.append(value)
        return result

    def eval_m2m_value(self, values):
        for key, vals in values.iteritems():
            if isinstance(vals, str) and vals.startswith('['):
                vals = eval(vals)
            values[key] = vals
        values = self.set_m2m_value(values)
        return values

    def set_m2m_value(self, values):
        new_vals = []
        for key, vals in values.iteritems():
            if isinstance(vals, list):
                for index, item in enumerate(vals):
                    if item.isdigit():
                        vals[index] = int(item)
                    new_vals.append((4, vals[index]))
                values[key] = new_vals
        return values


class Instance(RPCmethods, Parserdata):

    def __init__(self,  config_file_yml, url=None, port=8069, username=None,
                 password=None, dbname=False, load_config='ws_config.conf'):
        RPCmethods.__init__(self, url=url, port=port, username=username,
                            password=password, dbname=dbname,
                            load_config=load_config)
        Parserdata.__init__(self, config_file_yml)
        self.process = self.sort_process()
        self.login()
        self.create_data()

    def query_load_data(self, model, search, values, write=False):
        if values:
            values = self.eval_m2m_value(values)
        result = super(Instance, self).query_load_data(model, search, values, write)
        return result

    def sort_process(self):
        """
        Method orders the processes from the indicated sequence
        return: list
        """
        result = [(process, self.data[process].get("sequence"))
                  for process in self.data]
        result = sorted(result, key=lambda x: x[1])
        result = [res[0] for res in result]
        return result

    def conver_type(self, res, ttype):
        if ttype == 'int' and isinstance(res, list):
            res = res[0]
        elif ttype == 'list' and isinstance(res, int):
            res = [res]
        return res

    def add_data_xml_id(self, xml_id, values):
        env = self.conection.env.ref(xml_id)
        values = self.set_m2m_value(values)
        env.write(values)

    def create_data_xml_id(self, values):
        for value in values:
            self.add_data_xml_id(*value)

    def generate_result(self, model, res_id, result):
        """
        This method reads the key resulting from a given process, runs a
        browse to bring a record and updates the dictionary with
        the value of the fields specified in the result field,
        in case of not bringing the result key adds a default
        model: string
        res_id: int
        result: dict
        return: dict
        """
        if not result:
            result = {'id': 'int'}
        recordset = self.execute(model, 'browse', (res_id,))
        for res in result:
            result[res] = getattr(recordset, res)
        return Brouwseresult(model, (), result)

    def create_data(self):
        """
        This method is the one that starts with data loading, this
        traverses the attribute self.process which has in sequence
        the sequences of defined concerns
        return: None
        """
        for process_key in self.process:
            logging.info('Running process {}'.format(process_key))
            process = self.data.get(process_key)
            depends = process.get("depends")
            if depends:
                try:
                    render_value = self.render_depends_values(depends, process)
                except exceptions.TemplateAssertionError, error:
                    logging.error('Process interrupted {process} {error}'.
                                  format(process=process_key, error=error))
                    raise error
                process = render_value
            search = self.eval_parameters(process.get("search", []))
            values = process.get("values")
            model = process.get("model")
            write = process.get("write", False)
            add_data_xml_id = process.get("add_data_xml_id", False)
            if add_data_xml_id:
                self.create_data_xml_id(values)
            if model:
                res_id = self.query_load_data(model, search, values, write)
                new_result = self.generate_result(model, res_id,
                                                  process.get("result"))
                process.update({'result': new_result})
                self.data[process_key].update(process)
