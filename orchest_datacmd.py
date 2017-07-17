# coding: utf-8
import click
from ws_data_orchest import Instance


@click.group()
def cli():
    pass


@cli.command()
@click.option("-c", "--login_file", help="File configure loggin",
              default=False, required=False)
@click.option("-u", "--username", help="User for server odoo",
              default=False, required=False)
@click.option("-w", "--password", help="Password for server odoo",
              default=False, required=False)
@click.option("-p", "--port", help="Server port odoo",
              default=False, required=False)
@click.option("-h", "--host", help="Server url odoo",
              default=False, required=False)
@click.option("-d", "--dbname", help="Server dbname odoo",
              default=False, required=False)
@click.option("-f", "--file_data", help="Specify the file where the"
                                        " demo data is in yml format",
              default=False, required=True)
def load_data(login_file, username, password, port, host, dbname, file_data):
    """
    Method used to instantiate the class instances and receive the parameters
    via command line
    """
    if not file_data:
        click.echo("You must specify the file with the demo data")
        exit(1)
    Instance(file_data, username=username, password=password,
             port=port, url=host, dbname=dbname, load_config=login_file)
if __name__ == '__main__':
    load_data()
