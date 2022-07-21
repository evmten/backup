from email.utils import localtime
from azure.mgmt.compute import ComputeManagementClient
from azure.identity import AzureCliCredential
import sys

resource_group = 'xcc-assessment-efi'
subscription_id = '31169275-2308-4cdd-8d7a-f39ffd65bbf8'


def create_client(subscription_id):
    credential = AzureCliCredential()
    compute_client = ComputeManagementClient(credential, subscription_id)

    return compute_client

def fetch_vms(resource_group, subscription_id):
    compute_client = create_client(subscription_id)
    instances = [vm for vm in compute_client.virtual_machines.list(resource_group_name = resource_group)]

    return instances

def fetch_snapshots(resource_group, subscription_id):
    compute_client = create_client(subscription_id)
    snapshots = [snapshot for snapshot in compute_client.snapshots.list_by_resource_group(resource_group_name = resource_group)]

    return snapshots

compute_client = create_client(subscription_id)


try:
    subprocess_name = sys.argv[1]

    if(subprocess_name == "snapshot"):
        print("Starting backup process")
        print("Found " + str(len(fetch_vms(resource_group, subscription_id))) + " instances")
        for vm in fetch_vms(resource_group, subscription_id):
            print("Instance: " + vm.name +"-instance")
            print("Backup Enabled: " + vm.tags['backup']) 

            if vm.tags['backup'] == 'true':
                for snapshot in fetch_snapshots(resource_group, subscription_id):  
                    
                    print("Last Backup was " + str((localtime()-snapshot.time_created)) + " ago")

                    if ((localtime()-snapshot.time_created).total_seconds() < 86400): 
                        print("Skipping backup creation since the last backup is too recent")
                    else:
                        # Create asynchronous backup
                        print("Starting asynchronous backup creation")
                        
                        # print(len(compute_client.virtual_machines.instance_view(resource_group, vm.name).statuses))
                        for snapshot in fetch_snapshots(resource_group,subscription_id):
                            
                            managed_disk = compute_client.disks.get(resource_group, vm.storage_profile.os_disk.name)
                            
                            #Doesn't work
                            async_snapshot_creation = compute_client.snapshots.begin_create_or_update(
                                resource_group,
                                snapshot.name,
                                {
                                    'location': vm.location,
                                    'creation_data': {
                                        'create_option': 'Copy',
                                        'source_uri': managed_disk.id
                                    }
                                }
                                )
                            snapshot = async_snapshot_creation.result()

                            vm.tags['backup'] = 'true'
        else:
            # Create a backup
            print("Snapshot for disk " + vm.name + "-instance is Status")


    elif(subprocess_name == "apply-retention-policy"):
        
        #BACKUP -3
        print("Checking backups against retention policy")

        for vm in fetch_vms(resource_group, subscription_id):
            print("Checking backups for disk " + vm.name)

            for snapshot in fetch_snapshots(resource_group, subscription_id):
                date = snapshot.time_created.date()
                name = snapshot.name

                
                for snapshot in fetch_snapshots(resource_group, subscription_id):

                    # No more than one backup per day should be kept (last 7 days)
                    if (date == snapshot.time_created.date()) & (name != snapshot.name):

                        print("Deleting snapshot" + snapshot.name)
                        #Not sure if it works
                        compute_client.snapshots.begin_delete(
                        resource_group,
                        snapshot.name
                        )
                
                    # No more than one backup per week should be kept
                    elif (date.isocalendar()[1] == snapshot.time_created.date().isocalendar()[1] & (name != snapshot.name)):

                        print("Deleting snapshot" + snapshot.name)
                        #Not sure if it works
                        compute_client.snapshots.begin_delete(
                        resource_group,
                        snapshot.name
                        )
                    
                    else:

                        print("There is no backups against retention policy")
    else:
        print('Wrong subprocess name')

except IndexError: 
    #BACKUP -1

    print ("{:<15} {:<20} {:<15} {:<20}".format('Instance','Backup Enabled','Disk','Last Backup'))
    for vm in fetch_vms(resource_group, subscription_id):

        if (vm.tags['backup'])=='true':
            last_backup = str(vm.time_created)
        else:
            last_backup = 'Never'
        
        print ("{:<15} {:<20} {:<15} {:<20}".format(vm.name, vm.tags['backup'], vm.storage_profile.os_disk.name, last_backup))