# Chain of Custody 이진 평가 게이트

공개 fixture는 합성 데이터만 사용한다. 각 항목은 Y/N이며 하나라도 N이면 배포하지 않는다.

## 실행 게이트

- [ ] `python3 -m unittest discover -s skill-custody/tests -p 'test_*.py' -v`가 테스트 1건 이상을 실행하고 전부 PASS했는가?
- [ ] 정상 ledger가 `status=PASS`, event count > 0, artifact reference count > 0을 반환하는가?
- [ ] artifact 한 바이트 변조가 `artifact digest mismatch`로 실패하는가?
- [ ] event 삭제가 receipt count/digest 또는 chain 불일치로 실패하는가?
- [ ] event 순서 변경이 index/previous hash 불일치로 실패하는가?
- [ ] `previous_event_hash` 변조가 실패하는가?
- [ ] unknown provider를 넣고 event hash와 receipt까지 다시 계산해도 provider 검증이 실패하는가?
- [ ] credential 및 메시징 식별자가 원장에 평문으로 남지 않는가?
- [ ] key 삽입 순서가 다른 동치 객체의 canonical JSON과 hash가 동일한가?
- [ ] repo-relative POSIX path는 통과하고 절대경로·상위이동·역슬래시는 실패하는가?
- [ ] Pareto cohort/metric/code/model/provider 중 하나라도 불일치하면 `INCOMPARABLE`인가?

## 보안 게이트

- [ ] fixture와 문서에 개인 절대경로, 내부 artifact, 실 credential, 실제 메시지 metadata가 0건인가?
- [ ] ledger는 artifact 원문을 포함하지 않고 digest와 portable locator만 포함하는가?
- [ ] verifier가 unknown field를 이용한 provider 우회나 non-canonical JSON을 허용하지 않는가?

## 판정

모든 항목 Y일 때만 PASS다. 테스트 수 0, artifact reference 수 0, fixture 미적용은 `NOT_EXECUTED`이며 PASS로 승격하지 않는다.
