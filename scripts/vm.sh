#!/usr/bin/env bash
# The VM (ssh host Server_2, ~/q2q) is prod: it runs the router and the operator under systemd.
#   scripts/vm.sh code     push committed code and strategies (not arms.toml: the operator on the VM owns it)
#   scripts/vm.sh arms     push the local arms.toml
#   scripts/vm.sh models   push models/*.txt and *.json (the router reloads them on change)
#   scripts/vm.sh pull     fetch the VM's arms.toml
#   scripts/vm.sh sync     fetch what the dashboard shows: arms.toml, the operator's log and updates, a status line
#   scripts/vm.sh status   services, memory and the router's last lines
set -e
cd "$(dirname "$0")/.."
H=Server_2
case "$1" in
  code)   git archive HEAD | ssh $H 'tar x -C ~/q2q --exclude=arms.toml --exclude=updates.jsonl' ;;
  arms)   scp -q arms.toml $H:q2q/arms.toml.new && ssh $H 'mv ~/q2q/arms.toml.new ~/q2q/arms.toml' ;;
  models) tar cf - models/*.txt models/*.json | ssh $H 'mkdir -p ~/q2q/.in && tar x -C ~/q2q/.in && mv ~/q2q/.in/models/* ~/q2q/models/' ;;
  pull)   scp -q $H:q2q/arms.toml arms.toml ;;
  sync)   ssh $H 'cd ~/q2q && tar cf - arms.toml updates.jsonl logs/operator.out.log' | tar x -C logs/vm 2>/dev/null || { mkdir -p logs/vm; exit 1; }
          cp logs/vm/arms.toml arms.toml; cp logs/vm/logs/operator.out.log logs/operator.out.log
          ssh $H 'echo "$(date -u +%H:%M:%S) UTC | router $(systemctl is-active q2q-router) | operator $(systemctl is-active q2q-operator) | memory free $(free -m | awk "NR==2{print \$7}") MB, swap used $(free -m | awk "NR==3{print \$3}") MB | $(grep "^answered" ~/q2q/logs/router.out.log | tail -n 1 | sed "s/ arms {[^}]*}//")"' > logs/vm/status.txt ;;
  status) ssh $H 'systemctl is-active q2q-router q2q-operator; free -m | sed -n 2,3p; grep "^answered" ~/q2q/logs/router.out.log | tail -n 2; tail -n 2 ~/q2q/logs/operator.out.log; head -8 ~/q2q/arms.toml' ;;
  *) sed -n 2,8p "$0" ;;
esac
