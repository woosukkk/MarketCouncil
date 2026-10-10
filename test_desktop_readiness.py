import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from desktop.readiness import check_readiness, stage_for_line
from desktop.main import Output

class ReadinessTests(unittest.TestCase):
    def test_readiness_never_transmits_key_and_requires_no_docker_if_external_search_available(self) -> None:
        response=Mock();response.__enter__=Mock(return_value=Mock(status=200));response.__exit__=Mock(return_value=False)
        with tempfile.TemporaryDirectory() as folder,patch('desktop.readiness.urlopen',return_value=response) as network,patch('desktop.readiness.shutil.which',return_value=None),patch('desktop.readiness.subprocess.run') as command:
            rows=dict(check_readiness('private-key','https://search.example',Path(folder)))
            self.assertIn('입력됨',rows['OpenAI 키'])
            self.assertIn('외부 검색',rows['Docker'])
            network.assert_called_once_with('https://search.example',timeout=3)
            command.assert_not_called()
    def test_bad_url_missing_key_and_docker_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as folder,patch('desktop.readiness.urlopen') as network,patch('desktop.readiness.shutil.which',return_value='docker'),patch('desktop.readiness.subprocess.run',side_effect=__import__('subprocess').TimeoutExpired('docker',10)):
            rows=dict(check_readiness('','https://user:password@search.example',Path(folder)))
            network.assert_not_called()
            self.assertIn('입력 필요',rows['OpenAI 키']);self.assertIn('주소 확인',rows['검색 연결']);self.assertIn('시작 필요',rows['Docker'])
    def test_split_output_emits_stages_without_inventing_percentages(self) -> None:
        messages=queue.Queue();out=Output(messages)
        out.write('[공통 근거 수');out.write('집 시작]');out.write('\n')
        events=list(messages.queue)
        self.assertTrue(any(isinstance(event,tuple) and event[0]=='stage' for event in events))
        self.assertIn('2라운드',stage_for_line('[토론 2라운드 하락 관점 반론 시작]'))
        self.assertIsNone(stage_for_line('[WARN] random error'))
if __name__=='__main__':unittest.main()

