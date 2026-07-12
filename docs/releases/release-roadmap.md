# Easy MCF - Release Roadmap

## Scope

Easy MCF is a platform to streamline the job search and application process for job seekers in Singapore using [MyCareerFutures](http://mycareersfuture.gov.sg/) website

An early prototype version `jobsearch` is available for reference in the repo `jobsearch/` with webscraping methods developed in python for automating the search and application process using `selenium` for python package.  


| repo        | version   | description             |
| ----------- | --------- | ----------------------- |
| jobsearch   | 20250705  | prototype local         |
| easymcf     | 010       | POC local               |
| easymcf     | 020       | MVP cloud               |
| easymcf     | 100       | Beta single user        |  

__features__

| id | feature              | prototype local    | poc local       | mvp cloud        | beta single user        |
| -- | -------------------- | ------------------ | --------------- | ---------------- | ----------------------- |
| 01 | be runtime           | python             | python          | python           | python                  |
| 02 | fe runtime           | google sheets      | angular js      | angular js       | angular js              |
| 03 | database             | sqlite + gs        | sqlite          | aws sql          | aws sql                 |
| 04 | be deploy            | local              | local           | aws api gateway  | aws api gateway         |
| 05 | fe deploy            | google sheets      | local           | aws ec2          | aws ec2                 |
| 06 | search by keywords   | yes                | yes             | yes              | yes                     |
| 07 | crm pipeline         | yes                | yes             | yes              | yes                     |
| 08 | automated apply      | yes                | yes             | yes              | yes                     |

