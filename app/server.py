from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from time import sleep
from app import logger
import app.handling as handling
import re

def _get_project_id(uri):
    '''Try to get project ID from URI, return None if not found'''
    match = re.match(r'/smrt-link/projects/(\d+)', uri)
    if match:
        return int(match.group(1))
    else:
        return None
   
class RequestHandler(BaseHTTPRequestHandler):
    '''
    Respond to and log requests, then handle them asynchronously
    '''
    def _log_request(self, response_code):
        '''Log the request. Due for a re-design next time a new type of request
        needs to be supported.
        '''
        if response_code == 200:
            if self.command == 'POST':
                if self.path == '/smrt-link/projects':
                    logger.info(f'Received notification that a new project was created in SMRT Link')
                elif self.path == '/smrt-link/job-manager/jobs/analysis':
                    logger.info(f'Received notification that a new analysis job was created in SMRT Link')
                else:
                    logger.info(f'Received request: {self.command} {self.path}')
            elif self.command == 'PUT':
                logger.info(f'Received notification that project {self.project_id} was modified in SMRT Link')
            elif self.command == 'DELETE':
                logger.info(f'Received notification that project {self.project_id} was deleted in SMRT Link')
            else:
                logger.info(f'Received request: {self.command} {self.path}')
        elif response_code == 405:
            logger.info(f'Received request concerning project 1, which is not supported.')
        else:
            logger.info(f'Received invalid request: {self.command} {self.path}')
    
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self._log_request(200)
        self.wfile.write(b'smrtlink-share app is online')

    def _get_response_code(self):
        '''Return the appropriate response code for the request
        given the method and path of the request.
        '''
        assert self.command in ('POST', 'PUT', 'DELETE')
        if self.command in ('PUT', 'DELETE'):
            if self.project_id:
                if self.project_id == 1:
                    return 405 # project 1 should not be shared
                return 200
            return 404
        else: # POST
            if self.path == '/smrt-link/projects' or \
                self.path == '/smrt-link/job-manager/jobs/analysis':
                return 200
            else:
                return 404
            
    def handle_response(self):
        response_code = self._get_response_code()
        self.send_response(response_code) # RESPOND to client/proxy
        self.end_headers()
        self._log_request(response_code) # LOG the request
        if response_code != 200:
            return False
        return True
    
    def parse_request(self) -> bool:
        '''
        Method called by superclass init to validate request and set
        some attributes. I'm overriding this instead of init because 
        the superclass init also calls the do_* methods, which need 
        the project_id attribute to be set.
        '''
        request_is_valid = super().parse_request()
        self.project_id = _get_project_id(self.path)
        return request_is_valid
    
    def do_PUT(self):
        if not self.handle_response():
            return
        sleep(1)
        handling.update_project(self.project_id)        
    
    def do_POST(self):
        if not self.handle_response():
            return
        sleep(1)
        if self.path == '/smrt-link/projects':
            handling.new_project()
        elif self.path == '/smrt-link/job-manager/jobs/analysis':
            handling.update_analyses()
        else:
            logger.error(f'Unexpected POST request: {self.path}')
        
    def do_DELETE(self):
        if not self.handle_response():
            return
        handling.delete_project(self.project_id)

class App(ThreadingHTTPServer):

    def __init__(self, server_address):
        super().__init__(server_address, RequestHandler)

    def run(self):
        self.serve_forever()

    def stop(self):
        self.shutdown()