
from aiosmb.commons.interfaces.file import SMBFile
from aiosmb.commons.interfaces.blocking.file.protocol import *

class SMBBlockingFileMgr:
	"""
	This class implamanets a file object manager which can open/read/write files over the smbconnection
	The input/output queues used for communicating are process/thread/async safe!
	Therefore this creates a bridge between a non-async thread/process and the smb connection (file ops only!)
	"""
	def __init__(self, connection, in_q, out_q):
		self.connection = connection
		self.in_q = in_q
		self.out_q = out_q
		self.filehandle = {}
		self.curhandle = 0

	async def run(self):
		while True:
			try:
				cmd = await self.in_q.coro_get()
				if cmd.cmd_type == SMBFILECMD.OPEN:
					try:
						sf = SMBFile.from_remotepath(self.connection, cmd.path)
						await sf.open(self.connection, cmd.mode)
						self.filehandle[self.curhandle] = sf
						self.curhandle += 1
						res = SMBFileOpenReply(cmd.cmd_id, self.curhandle -1)
						await self.out_q.coro_put(res)
					except Exception as e:
						res = SMBFileError(cmd.cmd_id, str(e))
						await self.out_q.coro_put(res)

				elif cmd.cmd_type == SMBFILECMD.READ:
					try:
						sf = self.filehandle.get(cmd.handle)
						await sf.seek(cmd.position, 0)
						data = await sf.read(cmd.count)
						res = SMBFileReadReply(cmd.cmd_id, cmd.handle, data)
						await self.out_q.coro_put(res)
					except Exception as e:
						res = SMBFileError(cmd.cmd_id, str(e))
						await self.out_q.coro_put(res)

				elif cmd.cmd_type == SMBFILECMD.CLOSE:
					try:
						sf = self.filehandle.get(cmd.handle)
						await sf.close()
						del self.filehandle[cmd.handle]
						res = SMBFileCloseReply(cmd.cmd_id, cmd.handle)
						await self.out_q.coro_put(res)
					except Exception as e:
						res = SMBFileError(cmd.cmd_id, str(e))
						await self.out_q.coro_put(res)

				elif cmd.cmd_type == SMBFILECMD.WRITE:
					try:
						sf = self.filehandle.get(cmd.handle)
						await sf.seek(cmd.position, 0)
						count = await sf.write(cmd.data)
						del self.filehandle[cmd.handle]
						res = SMBFileWriteReply(cmd.cmd_id, cmd.handle, count)
						await self.out_q.coro_put(res)
					except Exception as e:
						res = SMBFileError(cmd.cmd_id, str(e))
						await self.out_q.coro_put(res)

				elif cmd.cmd_type == SMBFILECMD.TERMINATE:
					for handle in self.filehandle:
						sf = self.filehandle[handle]
						await sf.close()
						del self.filehandle[handle]
					return
			except Exception as e:
				res = SMBFileError(cmd.cmd_id, str(e))
				await self.out_q.coro_put(res)
				return
